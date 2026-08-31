"""Render the browser's carousel model into Instagram-compatible JPEG files."""

from __future__ import annotations

import base64
import binascii
import io
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps, UnidentifiedImageError

CANVAS_SIZE = (1080, 1350)
MAX_PHOTO_BYTES = 10 * 1024 * 1024
ALLOWED_PHOTO_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


class RenderError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RenderedMedia:
    path: Path
    public_url: str


class CarouselRenderer:
    def __init__(self, media_dir: Path, public_base_url: str, handle: str) -> None:
        self.media_dir = media_dir
        self.public_base_url = public_base_url.rstrip("/")
        self.handle = handle
        self.media_dir.mkdir(parents=True, exist_ok=True)

    def render(
        self,
        slides: list[list[str]],
        *,
        title: str = "",
        photo_data_url: str = "",
    ) -> list[RenderedMedia]:
        if not slides:
            raise RenderError("Yayınlanacak şiir karesi bulunamadı.")
        photo = decode_photo_data_url(photo_data_url) if photo_data_url else None
        total = len(slides) + int(photo is not None)
        if total > 10:
            raise RenderError("Instagram gönderisi en fazla 10 kare olabilir.")

        self.cleanup_expired()
        rendered: list[RenderedMedia] = []
        for index, lines in enumerate(slides):
            image = self._poem_slide(
                lines,
                title=title if index == 0 else "",
                photo=photo,
                index=index + 1,
                total=total,
            )
            rendered.append(self._save(image))
        if photo is not None:
            rendered.append(self._save(self._photo_slide(photo)))
        return rendered

    def delete(self, rendered: list[RenderedMedia]) -> None:
        for item in rendered:
            try:
                item.path.unlink(missing_ok=True)
            except OSError:
                pass

    def cleanup_expired(self, max_age_seconds: int = 24 * 60 * 60) -> None:
        cutoff = time.time() - max_age_seconds
        for path in self.media_dir.glob("*.jpg"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                continue

    def _poem_slide(
        self,
        lines: list[str],
        *,
        title: str,
        photo: Image.Image | None,
        index: int,
        total: int,
    ) -> Image.Image:
        image = _background(photo)
        draw = ImageDraw.Draw(image)
        poem_font = _fit_poem_font(draw, lines, max_width=850, max_height=660)
        title_font = _font("sans-bold", 34)
        meta_font = _font("sans-bold", 26)

        line_metrics = [draw.textbbox((0, 0), line, font=poem_font) for line in lines]
        line_heights = [box[3] - box[1] for box in line_metrics]
        gap = max(20, poem_font.size // 2)
        poem_height = sum(line_heights) + gap * max(0, len(lines) - 1)
        title_space = 80 if title else 0
        y = (CANVAS_SIZE[1] - poem_height - title_space) // 2 + title_space

        if title:
            title_box = draw.textbbox((0, 0), title.upper(), font=title_font)
            title_width = title_box[2] - title_box[0]
            draw.text(
                ((CANVAS_SIZE[0] - title_width) / 2, y - 94),
                title.upper(),
                fill=(241, 197, 173),
                font=title_font,
            )

        for line, box, height in zip(lines, line_metrics, line_heights):
            width = box[2] - box[0]
            draw.text(
                ((CANVAS_SIZE[0] - width) / 2, y),
                line,
                fill=(255, 253, 247),
                font=poem_font,
                stroke_width=1,
                stroke_fill=(15, 18, 16),
            )
            y += height + gap

        draw.text((76, 1260), self.handle, fill=(235, 235, 228), font=meta_font)
        counter = f"{index:02d} / {total:02d}"
        counter_box = draw.textbbox((0, 0), counter, font=meta_font)
        draw.text(
            (CANVAS_SIZE[0] - 76 - (counter_box[2] - counter_box[0]), 1260),
            counter,
            fill=(205, 205, 198),
            font=meta_font,
        )
        return image

    @staticmethod
    def _photo_slide(photo: Image.Image) -> Image.Image:
        canvas = Image.new("RGB", CANVAS_SIZE, (31, 31, 30))
        contained = ImageOps.contain(photo.convert("RGB"), CANVAS_SIZE, Image.Resampling.LANCZOS)
        offset = (
            (CANVAS_SIZE[0] - contained.width) // 2,
            (CANVAS_SIZE[1] - contained.height) // 2,
        )
        canvas.paste(contained, offset)
        return canvas

    def _save(self, image: Image.Image) -> RenderedMedia:
        filename = f"{uuid.uuid4().hex}.jpg"
        path = self.media_dir / filename
        # Meta processes images after accepting the media-container request.
        # Baseline RGB JPEGs are the most interoperable input for that processor;
        # progressive JPEGs can pass local validation and the initial API request
        # but later fail with media error 9004 / subcode 2207052.
        image.convert("RGB").save(
            path,
            format="JPEG",
            quality=94,
            subsampling=0,
            optimize=False,
            progressive=False,
        )
        return RenderedMedia(
            path=path,
            public_url=f"{self.public_base_url}/media/{filename}",
        )


def decode_photo_data_url(data_url: str) -> Image.Image:
    try:
        header, encoded = data_url.split(",", maxsplit=1)
        mime_type = header.removeprefix("data:").split(";", maxsplit=1)[0]
        if mime_type not in ALLOWED_PHOTO_MIME_TYPES or ";base64" not in header:
            raise RenderError("Fotoğraf JPG, PNG veya WebP biçiminde olmalıdır.")
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > MAX_PHOTO_BYTES:
            raise RenderError("Fotoğraf 10 MB'den küçük olmalıdır.")
        image = Image.open(io.BytesIO(raw))
        image.load()
        return ImageOps.exif_transpose(image).convert("RGB")
    except RenderError:
        raise
    except (ValueError, binascii.Error, UnidentifiedImageError, OSError) as error:
        raise RenderError("Fotoğraf dosyası okunamadı.") from error


def _background(photo: Image.Image | None) -> Image.Image:
    if photo is not None:
        image = ImageOps.fit(photo.convert("RGB"), CANVAS_SIZE, Image.Resampling.LANCZOS)
        image = image.filter(ImageFilter.GaussianBlur(radius=18))
        image = ImageEnhance.Brightness(image).enhance(0.37)
    else:
        image = Image.new("RGB", CANVAS_SIZE)
        draw = ImageDraw.Draw(image)
        top = (54, 76, 62)
        bottom = (25, 31, 27)
        for y in range(CANVAS_SIZE[1]):
            ratio = y / (CANVAS_SIZE[1] - 1)
            color = tuple(round(a + (b - a) * ratio) for a, b in zip(top, bottom))
            draw.line((0, y, CANVAS_SIZE[0], y), fill=color)
    overlay = Image.new("RGBA", CANVAS_SIZE, (4, 7, 5, 40))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def _fit_poem_font(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    *,
    max_width: int,
    max_height: int,
) -> ImageFont.FreeTypeFont:
    for size in range(64, 27, -2):
        font = _font("serif", size)
        boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
        width = max((box[2] - box[0] for box in boxes), default=0)
        heights = [box[3] - box[1] for box in boxes]
        height = sum(heights) + max(20, size // 2) * max(0, len(lines) - 1)
        if width <= max_width and height <= max_height:
            return font
    fallback = _font("serif", 28)
    fallback_boxes = [draw.textbbox((0, 0), line, font=fallback) for line in lines]
    if max((box[2] - box[0] for box in fallback_boxes), default=0) > max_width:
        raise RenderError("Bir şiir satırı görsele sığmayacak kadar uzun.")
    return fallback


def _font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    candidates = {
        "serif": [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "DejaVuSerif.ttf",
        ],
        "sans-bold": [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "DejaVuSans-Bold.ttf",
        ],
    }
    for candidate in candidates[kind]:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    raise RenderError("Gerekli DejaVu yazı tipi bulunamadı.")
