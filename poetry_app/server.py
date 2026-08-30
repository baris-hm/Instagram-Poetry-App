"""Dependency-free HTTP layer for the poetry carousel prototype."""

from __future__ import annotations

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .poem_divider import DEFAULT_LINES_PER_SLIDE, divide_poem

LOGGER = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).with_name("static")
MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_CAROUSEL_SLIDES = 10
SUPPORTED_LINES_PER_SLIDE = {2, DEFAULT_LINES_PER_SLIDE}

_STATIC_ROUTES: dict[str, tuple[Path, str]] = {
    "/": (STATIC_DIR / "index.html", "text/html; charset=utf-8"),
    "/preview": (STATIC_DIR / "index.html", "text/html; charset=utf-8"),
    "/static/styles.css": (STATIC_DIR / "styles.css", "text/css; charset=utf-8"),
    "/static/app.js": (STATIC_DIR / "app.js", "text/javascript; charset=utf-8"),
}


class PoetryRequestHandler(BaseHTTPRequestHandler):
    """Serve the app shell and a small JSON preview endpoint."""

    server_version = "PoetryCarousel/0.1"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.split("?", maxsplit=1)[0]
        if path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return

        route = _STATIC_ROUTES.get(path)
        if route is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Sayfa bulunamadı."})
            return

        file_path, content_type = route
        self._send_bytes(HTTPStatus.OK, file_path.read_bytes(), content_type)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.split("?", maxsplit=1)[0]
        if path != "/api/preview":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Sayfa bulunamadı."})
            return

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

            lines_per_slide = payload.get(
                "lines_per_slide",
                DEFAULT_LINES_PER_SLIDE,
            )
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

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ValueError("İstek içeriği eksik.")

        length = int(raw_length)
        if length > MAX_REQUEST_BYTES:
            raise ValueError("Şiir metni bu prototip için çok büyük.")

        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("İstek bir nesne olmalıdır.")
        return payload

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _send_bytes(
        self,
        status: HTTPStatus,
        body: bytes,
        content_type: str,
    ) -> None:
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
    """HTTP server with prompt socket reuse during local development."""

    allow_reuse_address = True


def create_server(host: str = "127.0.0.1", port: int = 8000) -> PoetryServer:
    return PoetryServer((host, port), PoetryRequestHandler)


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    server = create_server(host=host, port=port)
    LOGGER.info("Şiirden Karelere: http://%s:%s", host, server.server_port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Sunucu durduruldu.")
    finally:
        server.server_close()
