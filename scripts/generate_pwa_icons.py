"""Generate the installable app icons from the existing Ş brand mark."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "poetry_app" / "static" / "icons"

PAPER = "#f5f0e7"
ACCENT = "#a13d2d"
INK = "#fffaf1"


def _font(size: int) -> ImageFont.FreeTypeFont:
    candidates = (
        Path("C:/Windows/Fonts/georgiab.ttf"),
        Path("C:/Windows/Fonts/georgia.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"),
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    raise FileNotFoundError("No suitable serif font was found for the app icon.")


def _draw_mark(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], color: str) -> None:
    """Draw the rounded brand tile with its distinct, tighter lower-left corner."""
    left, top, right, bottom = box
    width = right - left
    radius = int(width * 0.42)
    small_radius = int(width * 0.10)
    draw.rounded_rectangle(box, radius=radius, fill=color)

    # Extend the lower-left area, then restore the small corner curve.
    draw.rectangle((left + small_radius, top + width // 2, left + radius, bottom), fill=color)
    draw.rectangle((left, top + width // 2, left + radius, bottom - small_radius), fill=color)
    draw.pieslice(
        (left, bottom - 2 * small_radius, left + 2 * small_radius, bottom),
        90,
        180,
        fill=color,
    )


def _draw_letter(draw: ImageDraw.ImageDraw, size: int, fill: str) -> None:
    font = _font(round(size * 0.43))
    # Georgia's glyph sits slightly low optically; this adjustment centers the mark.
    draw.text(
        (size / 2, size * 0.485),
        "Ş",
        font=font,
        fill=fill,
        anchor="mm",
        stroke_width=max(0, size // 256),
        stroke_fill=fill,
    )


def create_icon(size: int, *, maskable: bool = False) -> Image.Image:
    scale = 4
    canvas_size = size * scale
    background = ACCENT if maskable else PAPER
    image = Image.new("RGB", (canvas_size, canvas_size), background)
    draw = ImageDraw.Draw(image)

    if maskable:
        _draw_letter(draw, canvas_size, INK)
    else:
        margin = round(canvas_size * 0.11)
        _draw_mark(draw, (margin, margin, canvas_size - margin, canvas_size - margin), ACCENT)
        _draw_letter(draw, canvas_size, INK)

    return image.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for size in (64, 192, 512):
        create_icon(size).save(OUTPUT_DIR / f"icon-{size}.png", optimize=True)
    create_icon(512, maskable=True).save(
        OUTPUT_DIR / "icon-maskable-512.png",
        optimize=True,
    )


if __name__ == "__main__":
    main()
