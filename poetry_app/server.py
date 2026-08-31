"""HTTP application layer for composing and publishing poetry carousels."""

from __future__ import annotations

import json
import logging
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .instagram_client import InstagramAPIError
from .media_server import PublicMediaServer, create_media_server
from .poem_divider import DEFAULT_LINES_PER_SLIDE, divide_poem
from .publisher import InstagramPublishingService, PublishRequest, PublishValidationError
from .renderer import RenderError
from .settings import AppSettings

LOGGER = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).with_name("static")
MAX_REQUEST_BYTES = 16 * 1024 * 1024
MAX_CAROUSEL_SLIDES = 10
SUPPORTED_LINES_PER_SLIDE = {2, DEFAULT_LINES_PER_SLIDE}

_STATIC_ROUTES: dict[str, tuple[Path, str]] = {
    "/": (STATIC_DIR / "index.html", "text/html; charset=utf-8"),
    "/preview": (STATIC_DIR / "index.html", "text/html; charset=utf-8"),
    "/static/styles.css": (STATIC_DIR / "styles.css", "text/css; charset=utf-8"),
    "/static/app.js": (STATIC_DIR / "app.js", "text/javascript; charset=utf-8"),
}


class PoetryRequestHandler(BaseHTTPRequestHandler):
    """Serve the app shell and JSON application endpoints."""

    server_version = "PoetryCarousel/0.2"

    @property
    def settings(self) -> AppSettings:
        return self.server.settings  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.split("?", maxsplit=1)[0]
        if path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if path == "/api/config":
            self._handle_config()
            return

        route = _STATIC_ROUTES.get(path)
        if route is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Sayfa bulunamadı."})
            return

        file_path, content_type = route
        self._send_bytes(HTTPStatus.OK, file_path.read_bytes(), content_type)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.split("?", maxsplit=1)[0]
        if path == "/api/preview":
            self._handle_preview()
            return
        if path == "/api/publish":
            self._handle_publish()
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Sayfa bulunamadı."})

    def _handle_config(self) -> None:
        missing = self.settings.missing_publish_settings
        if not missing:
            message = "Instagram yayını hazır."
        elif "INSTAGRAM_ACCESS_TOKEN" in missing:
            message = "Instagram erişim anahtarı .env dosyasında ayarlanmalı."
        else:
            message = "Görseller için herkese açık bir HTTPS adresi ayarlanmalı."
        self._send_json(
            HTTPStatus.OK,
            {
                "instagram_handle": self.settings.instagram_handle,
                "publishing_enabled": self.settings.publishing_enabled,
                "message": message,
                "missing": list(missing),
            },
        )

    def _handle_preview(self) -> None:
        try:
            payload = self._read_json()
            poem = payload.get("poem", "")
            if not isinstance(poem, str) or not poem.strip():
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "Önizleme için şiirinizi yapıştırın."},
                )
                return

            title = payload.get("title", "")
            description = payload.get("description", "")
            if not isinstance(title, str) or not isinstance(description, str):
                raise ValueError("Başlık ve açıklama metin olmalıdır.")

            lines_per_slide = payload.get("lines_per_slide", DEFAULT_LINES_PER_SLIDE)
            if (
                not isinstance(lines_per_slide, int)
                or isinstance(lines_per_slide, bool)
                or lines_per_slide not in SUPPORTED_LINES_PER_SLIDE
            ):
                raise ValueError("Kare görünümü iki veya dört satır olmalıdır.")

            has_photo = payload.get("has_photo", False)
            if not isinstance(has_photo, bool):
                raise ValueError("Fotoğraf bilgisi doğru biçimde gönderilmelidir.")

            slides = divide_poem(poem, lines_per_slide=lines_per_slide)
            carousel_slide_count = len(slides) + int(has_photo)
            if lines_per_slide == 2 and carousel_slide_count > MAX_CAROUSEL_SLIDES:
                raise ValueError(
                    "Beyit görünümü fotoğrafla birlikte en fazla 10 kare olabilir."
                )

            self._send_json(
                HTTPStatus.OK,
                {
                    "title": title.strip(),
                    "description": description.strip(),
                    "carousel_slide_count": carousel_slide_count,
                    "lines_per_slide": lines_per_slide,
                    "max_carousel_slides": MAX_CAROUSEL_SLIDES,
                    "max_lines_per_slide": DEFAULT_LINES_PER_SLIDE,
                    "slides": slides,
                },
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "İstek okunamadı. Lütfen tekrar deneyin."},
            )
        except ValueError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def _handle_publish(self) -> None:
        if not self.settings.publishing_enabled:
            self._send_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "Instagram yayını için .env ayarları tamamlanmamış."},
            )
            return
        try:
            request = PublishRequest.from_payload(self._read_json())
            result = InstagramPublishingService(self.settings).publish(request)
            self._send_json(
                HTTPStatus.OK,
                {"message": "Gönderi Instagram'da yayınlandı.", **result},
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Yayın isteği okunamadı."})
        except (PublishValidationError, RenderError, ValueError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except InstagramAPIError as error:
            LOGGER.warning("Instagram publish failed: %s", error)
            self._send_json(HTTPStatus.BAD_GATEWAY, {"error": str(error)})
        except Exception:
            LOGGER.exception("Unexpected publishing failure")
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "Gönderi yayınlanırken beklenmeyen bir hata oluştu."},
            )

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ValueError("İstek içeriği eksik.")
        try:
            length = int(raw_length)
        except ValueError as error:
            raise ValueError("İstek boyutu geçersiz.") from error
        if length < 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("İstek bu prototip için çok büyük.")

        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("İstek bir nesne olmalıdır.")
        return payload

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _send_bytes(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' blob: data:; "
            "style-src 'self'; script-src 'self'; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        LOGGER.info("%s - %s", self.client_address[0], format % args)


class PoetryServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], settings: AppSettings) -> None:
        self.settings = settings
        super().__init__(address, PoetryRequestHandler)


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    settings: AppSettings | None = None,
) -> PoetryServer:
    return PoetryServer((host, port), settings or AppSettings.from_env())


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = AppSettings.from_env()
    app_server = create_server(host=host, port=port, settings=settings)
    media_server: PublicMediaServer | None = None
    media_thread: threading.Thread | None = None

    if settings.public_media_base_url:
        media_server = create_media_server(
            settings.media_dir,
            host=settings.media_host,
            port=settings.media_port,
        )
        media_thread = threading.Thread(target=media_server.serve_forever, daemon=True)
        media_thread.start()
        LOGGER.info(
            "Public media origin: http://%s:%s",
            settings.media_host,
            media_server.server_port,
        )

    LOGGER.info("Şiirden Karelere: http://%s:%s", host, app_server.server_port)
    if not settings.publishing_enabled:
        LOGGER.info("Instagram publishing is not configured; preview mode remains available.")
    try:
        app_server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Sunucu durduruldu.")
    finally:
        app_server.server_close()
        if media_server is not None:
            media_server.shutdown()
            media_server.server_close()
        if media_thread is not None:
            media_thread.join(timeout=2)

