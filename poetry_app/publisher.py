"""Application service that validates, renders, and publishes one post."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .instagram_client import InstagramClient
from .renderer import CarouselRenderer, RenderedMedia
from .settings import AppSettings


class PublishValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PublishRequest:
    slides: list[list[str]]
    title: str
    description: str
    photo_data_url: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PublishRequest":
        raw_slides = payload.get("slides")
        if not isinstance(raw_slides, list) or not raw_slides:
            raise PublishValidationError("Yayınlanacak şiir kareleri eksik.")

        slides: list[list[str]] = []
        for raw_slide in raw_slides:
            if not isinstance(raw_slide, list) or not 1 <= len(raw_slide) <= 4:
                raise PublishValidationError("Her şiir karesi 1 ile 4 satır içermelidir.")
            lines: list[str] = []
            for raw_line in raw_slide:
                if not isinstance(raw_line, str) or not raw_line.strip():
                    raise PublishValidationError("Şiir satırları boş olamaz.")
                if len(raw_line) > 500:
                    raise PublishValidationError("Bir şiir satırı çok uzun.")
                lines.append(raw_line.strip())
            slides.append(lines)

        title = payload.get("title", "")
        description = payload.get("description", "")
        photo_data_url = payload.get("photo_data_url", "")
        if not isinstance(title, str) or len(title) > 120:
            raise PublishValidationError("Başlık 120 karakterden kısa olmalıdır.")
        if not isinstance(description, str) or len(description) > 2200:
            raise PublishValidationError("Açıklama 2200 karakterden kısa olmalıdır.")
        if not isinstance(photo_data_url, str):
            raise PublishValidationError("Fotoğraf verisi geçersiz.")
        if len(slides) + int(bool(photo_data_url)) > 10:
            raise PublishValidationError("Instagram gönderisi en fazla 10 kare olabilir.")

        return cls(
            slides=slides,
            title=title.strip(),
            description=description.strip(),
            photo_data_url=photo_data_url,
        )


class InstagramPublishingService:
    def __init__(self, settings: AppSettings) -> None:
        if not settings.publishing_enabled:
            raise ValueError("Publishing settings are incomplete")
        self.settings = settings
        self.renderer = CarouselRenderer(
            settings.media_dir,
            settings.public_media_base_url,
            settings.instagram_handle,
        )
        self.client = InstagramClient(
            settings.instagram_access_token,
            api_version=settings.graph_api_version,
            base_url=settings.graph_api_base_url,
            user_id=settings.instagram_user_id,
        )

    def publish(self, request: PublishRequest) -> dict[str, str]:
        rendered: list[RenderedMedia] = []
        rendered = self.renderer.render(
            request.slides,
            title=request.title,
            photo_data_url=request.photo_data_url,
        )
        post = self.client.publish_images(
            [item.public_url for item in rendered],
            caption=request.description,
        )
        self.renderer.delete(rendered)
        return {"media_id": post.media_id, "permalink": post.permalink}
