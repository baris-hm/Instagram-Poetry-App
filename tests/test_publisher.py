import tempfile
import unittest
from pathlib import Path

from poetry_app.instagram_client import InstagramAPIError, PublishedPost
from poetry_app.publisher import (
    InstagramPublishingService,
    PublishRequest,
    PublishValidationError,
)
from poetry_app.renderer import RenderedMedia
from poetry_app.settings import AppSettings


class FakeRenderer:
    def __init__(self, rendered: list[RenderedMedia]) -> None:
        self.rendered = rendered
        self.deleted = False

    def render(self, slides, *, title="", photo_data_url=""):
        return self.rendered

    def delete(self, rendered):
        self.deleted = True


class FakeClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def publish_images(self, image_urls, caption=""):
        if self.error:
            raise self.error
        return PublishedPost("media-id", "https://www.instagram.com/p/example/")


class PublisherTests(unittest.TestCase):
    def make_service(self, directory: str) -> InstagramPublishingService:
        return InstagramPublishingService(
            AppSettings(
                instagram_access_token="token",
                public_media_base_url="https://media.example.test",
                media_dir=Path(directory),
            )
        )

    @staticmethod
    def request() -> PublishRequest:
        return PublishRequest(
            slides=[["Bir dize"]],
            title="",
            description="Açıklama",
            photo_data_url="",
        )

    def test_successful_publish_deletes_temporary_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self.make_service(directory)
            renderer = FakeRenderer(
                [RenderedMedia(Path(directory) / "image.jpg", "https://media.example.test/image.jpg")]
            )
            service.renderer = renderer
            service.client = FakeClient()

            result = service.publish(self.request())

        self.assertEqual(result["media_id"], "media-id")
        self.assertTrue(renderer.deleted)

    def test_failed_publish_keeps_media_available_for_instagram_or_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self.make_service(directory)
            renderer = FakeRenderer(
                [RenderedMedia(Path(directory) / "image.jpg", "https://media.example.test/image.jpg")]
            )
            service.renderer = renderer
            service.client = FakeClient(InstagramAPIError("publish failed"))

            with self.assertRaises(InstagramAPIError):
                service.publish(self.request())

        self.assertFalse(renderer.deleted)

    def test_publish_request_accepts_seven_line_bent_slide(self) -> None:
        lines = [f"Dize {number}" for number in range(1, 8)]

        request = PublishRequest.from_payload({"slides": [lines]})

        self.assertEqual(request.slides, [lines])

    def test_publish_request_rejects_more_than_seven_lines_per_slide(self) -> None:
        lines = [f"Dize {number}" for number in range(1, 9)]

        with self.assertRaises(PublishValidationError):
            PublishRequest.from_payload({"slides": [lines]})

    def test_publish_request_rejects_more_than_63_total_lines(self) -> None:
        slides = [
            [f"Dize {slide * 7 + line}" for line in range(1, 8)]
            for slide in range(10)
        ]

        with self.assertRaises(PublishValidationError):
            PublishRequest.from_payload({"slides": slides})


if __name__ == "__main__":
    unittest.main()
