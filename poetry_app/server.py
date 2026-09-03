"""HTTP application layer for composing and publishing poetry carousels."""

from __future__ import annotations

import json
import logging
import threading
from hmac import compare_digest
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from .auth import (
    SESSION_COOKIE_NAME,
    create_session_value,
    is_valid_session_value,
    session_from_cookie_header,
)
from .instagram_client import InstagramAPIError
from .media_server import PublicMediaServer, create_media_server, resolve_public_media_path
from .poem_divider import (
    BENT_LINE_COUNTS,
    DEFAULT_LINES_PER_SLIDE,
    MAX_BENT_SLIDES,
    divide_bent_poem,
    divide_poem,
    poem_lines,
)
from .publisher import InstagramPublishingService, PublishRequest, PublishValidationError
from .renderer import CANVAS_SIZE, CarouselRenderer, RenderError
from .settings import AppSettings

LOGGER = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).with_name("static")
MAX_REQUEST_BYTES = 16 * 1024 * 1024
MAX_CAROUSEL_SLIDES = 10
MAX_VERSES = 63
SUPPORTED_LINES_PER_SLIDE = {2, DEFAULT_LINES_PER_SLIDE}
SUPPORTED_LAYOUTS = {"couplet", "quatrain", "bent"}

_STATIC_ROUTES: dict[str, tuple[Path, str]] = {
    "/": (STATIC_DIR / "index.html", "text/html; charset=utf-8"),
    "/preview": (STATIC_DIR / "index.html", "text/html; charset=utf-8"),
    "/static/styles.css": (STATIC_DIR / "styles.css", "text/css; charset=utf-8"),
    "/static/app.js": (STATIC_DIR / "app.js", "text/javascript; charset=utf-8"),
    "/static/pwa.js": (STATIC_DIR / "pwa.js", "text/javascript; charset=utf-8"),
    "/static/icons/icon-64.png": (STATIC_DIR / "icons" / "icon-64.png", "image/png"),
    "/static/icons/icon-192.png": (STATIC_DIR / "icons" / "icon-192.png", "image/png"),
    "/static/icons/icon-512.png": (STATIC_DIR / "icons" / "icon-512.png", "image/png"),
    "/static/icons/icon-maskable-512.png": (
        STATIC_DIR / "icons" / "icon-maskable-512.png",
        "image/png",
    ),
}
_PUBLIC_APP_ROUTES: dict[str, tuple[Path, str]] = {
    "/manifest.webmanifest": (
        STATIC_DIR / "manifest.webmanifest",
        "application/manifest+json; charset=utf-8",
    ),
    "/service-worker.js": (
        STATIC_DIR / "service-worker.js",
        "text/javascript; charset=utf-8",
    ),
    "/offline": (STATIC_DIR / "offline.html", "text/html; charset=utf-8"),
}
LOGIN_PAGE = STATIC_DIR / "login.html"


class PoetryRequestHandler(BaseHTTPRequestHandler):
    """Serve the app shell and JSON application endpoints."""

    server_version = "PoetryCarousel/0.5"

    @property
    def settings(self) -> AppSettings:
        return self.server.settings  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.split("?", maxsplit=1)[0]
        if path.startswith("/media/"):
            self._handle_public_media(path, include_body=True)
            return
        if path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if path == "/login":
            self._handle_login_page()
            return
        if path in _PUBLIC_APP_ROUTES:
            self._handle_public_app_asset(path)
            return
        if path.startswith("/static/"):
            self._handle_static(path)
            return
        if not self._require_authenticated(path):
            return
        if path == "/api/config":
            self._handle_config()
            return

        self._handle_static(path)

    def _handle_public_app_asset(self, path: str) -> None:
        file_path, content_type = _PUBLIC_APP_ROUTES[path]
        self._send_bytes(HTTPStatus.OK, file_path.read_bytes(), content_type)

    def _handle_static(self, path: str) -> None:
        route = _STATIC_ROUTES.get(path)
        if route is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Sayfa bulunamadı."})
            return

        file_path, content_type = route
        self._send_bytes(HTTPStatus.OK, file_path.read_bytes(), content_type)

    def do_HEAD(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.split("?", maxsplit=1)[0]
        if path.startswith("/media/"):
            self._handle_public_media(path, include_body=False)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.split("?", maxsplit=1)[0]
        if path == "/login":
            self._handle_login()
            return
        if not self._require_authenticated(path):
            return
        if path == "/logout":
            self._handle_logout()
            return
        if path == "/api/preview":
            self._handle_preview()
            return
        if path == "/api/render-preview":
            self._handle_render_preview()
            return
        if path == "/api/publish":
            self._handle_publish()
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Sayfa bulunamadı."})

    def _handle_config(self) -> None:
        missing = self.settings.missing_publish_settings
        if not missing:
            message = "Instagram yayını hazır."
        elif "APP_AUTH" in missing:
            message = "Yayınlamadan önce uygulama erişimi korunmalıdır."
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

    def _handle_login_page(self) -> None:
        if self._is_authenticated():
            self._redirect("/")
            return
        has_error = "error=1" in self.path.split("?", maxsplit=1)[-1]
        body = LOGIN_PAGE.read_text(encoding="utf-8")
        body = body.replace("{{LOGIN_ERROR_HIDDEN}}", "" if has_error else "hidden")
        self._send_bytes(
            HTTPStatus.OK,
            body.encode("utf-8"),
            "text/html; charset=utf-8",
        )

    def _handle_login(self) -> None:
        if not self.settings.access_protection_enabled:
            self._redirect("/")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 0 < length <= 8192:
            self._redirect("/login?error=1", status=HTTPStatus.SEE_OTHER)
            return
        payload = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"))
        supplied_password = payload.get("password", [""])[0]
        if not compare_digest(supplied_password, self.settings.app_password):
            self._redirect("/login?error=1", status=HTTPStatus.SEE_OTHER)
            return

        session_value = create_session_value(
            self.settings.app_session_secret,
            self.settings.session_max_age_seconds,
        )
        cookie = (
            f"{SESSION_COOKIE_NAME}={session_value}; Path=/; "
            f"Max-Age={self.settings.session_max_age_seconds}; "
            "HttpOnly; Secure; SameSite=Strict"
        )
        self._redirect("/", status=HTTPStatus.SEE_OTHER, cookie=cookie)

    def _handle_logout(self) -> None:
        cookie = (
            f"{SESSION_COOKIE_NAME}=; Path=/; Max-Age=0; "
            "HttpOnly; Secure; SameSite=Strict"
        )
        self._redirect("/login", status=HTTPStatus.SEE_OTHER, cookie=cookie)

    def _is_authenticated(self) -> bool:
        if not self.settings.access_protection_enabled:
            return True
        value = session_from_cookie_header(self.headers.get("Cookie", ""))
        return is_valid_session_value(self.settings.app_session_secret, value)

    def _require_authenticated(self, path: str) -> bool:
        if self._is_authenticated():
            return True
        if path.startswith("/api/") or self.command != "GET":
            self._send_json(
                HTTPStatus.UNAUTHORIZED,
                {"error": "Oturumunuz sona erdi. Lütfen yeniden giriş yapın."},
            )
        else:
            self._redirect("/login")
        return False

    def _redirect(
        self,
        location: str,
        *,
        status: HTTPStatus = HTTPStatus.FOUND,
        cookie: str = "",
    ) -> None:
        self.send_response(status)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0")
        self.end_headers()

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

            verse_count = len(poem_lines(poem))
            if verse_count > MAX_VERSES:
                raise ValueError("Önizleme en fazla 63 dize destekler.")

            layout = payload.get("layout")
            if layout is None:
                # Keep the original API shape working for existing clients.
                if "lines_per_slide" in payload:
                    lines_per_slide = payload["lines_per_slide"]
                    if (
                        not isinstance(lines_per_slide, int)
                        or isinstance(lines_per_slide, bool)
                        or lines_per_slide not in SUPPORTED_LINES_PER_SLIDE
                    ):
                        raise ValueError("Kare görünümü iki veya dört satır olmalıdır.")
                    layout = "couplet" if lines_per_slide == 2 else "quatrain"
                else:
                    layout = "bent" if verse_count >= 37 else "quatrain"
            if not isinstance(layout, str) or layout not in SUPPORTED_LAYOUTS:
                raise ValueError("Kare görünümü dörtlük, beyit veya bent olmalıdır.")

            has_photo = payload.get("has_photo", False)
            if not isinstance(has_photo, bool):
                raise ValueError("Fotoğraf bilgisi doğru biçimde gönderilmelidir.")

            bent_mode: str | None = None
            if layout == "quatrain":
                if verse_count >= 37:
                    raise ValueError("37 veya daha fazla dizede Dörtlük görünümü kullanılamaz.")
                lines_per_slide: int | None = DEFAULT_LINES_PER_SLIDE
                max_lines_per_slide = DEFAULT_LINES_PER_SLIDE
                slides = divide_poem(poem, lines_per_slide=DEFAULT_LINES_PER_SLIDE)
            elif layout == "couplet":
                lines_per_slide = 2
                max_lines_per_slide = DEFAULT_LINES_PER_SLIDE
                slides = divide_poem(poem, lines_per_slide=2)
            else:
                raw_bent_mode = payload.get("bent_mode", "automatic")
                if raw_bent_mode == "automatic":
                    parsed_bent_mode: str | int = "automatic"
                    bent_mode = "automatic"
                    lines_per_slide = None
                elif (
                    isinstance(raw_bent_mode, int)
                    and not isinstance(raw_bent_mode, bool)
                    and raw_bent_mode in BENT_LINE_COUNTS
                ):
                    parsed_bent_mode = raw_bent_mode
                    bent_mode = str(raw_bent_mode)
                    lines_per_slide = raw_bent_mode
                elif isinstance(raw_bent_mode, str) and raw_bent_mode in {"5", "6", "7"}:
                    parsed_bent_mode = int(raw_bent_mode)
                    bent_mode = raw_bent_mode
                    lines_per_slide = parsed_bent_mode
                else:
                    raise ValueError("Bent düzeni Otomatik, 5'lik, 6'lık veya 7'lik olmalıdır.")

                if isinstance(parsed_bent_mode, int) and verse_count > parsed_bent_mode * MAX_BENT_SLIDES:
                    raise ValueError(
                        f"{parsed_bent_mode}'lik Bent düzeni en fazla "
                        f"{parsed_bent_mode * MAX_BENT_SLIDES} dize destekler."
                    )
                max_lines_per_slide = max(BENT_LINE_COUNTS)
                slides = divide_bent_poem(poem, mode=parsed_bent_mode)

            carousel_slide_count = len(slides) + int(has_photo)
            if carousel_slide_count > MAX_CAROUSEL_SLIDES:
                view_name = {
                    "couplet": "Beyit",
                    "quatrain": "Dörtlük",
                    "bent": "Bent",
                }[layout]
                raise ValueError(
                    f"{view_name} görünümü fotoğrafla birlikte en fazla 10 kare olabilir."
                )

            self._send_json(
                HTTPStatus.OK,
                {
                    "title": title.strip(),
                    "description": description.strip(),
                    "verse_count": verse_count,
                    "carousel_slide_count": carousel_slide_count,
                    "layout": layout,
                    "bent_mode": bent_mode,
                    "lines_per_slide": lines_per_slide,
                    "max_carousel_slides": MAX_CAROUSEL_SLIDES,
                    "max_lines_per_slide": max_lines_per_slide,
                    "max_verses": MAX_VERSES,
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

    def _handle_render_preview(self) -> None:
        try:
            request = PublishRequest.from_payload(self._read_json())
            renderer = CarouselRenderer(
                self.settings.media_dir,
                "",
                self.settings.instagram_handle,
            )
            rendered = renderer.render(
                request.slides,
                title=request.title,
                photo_data_url=request.photo_data_url,
            )
            self._send_json(
                HTTPStatus.OK,
                {
                    "preview_urls": [item.public_url for item in rendered],
                    "width": CANVAS_SIZE[0],
                    "height": CANVAS_SIZE[1],
                },
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "Önizleme isteği okunamadı."},
            )
        except (PublishValidationError, RenderError, ValueError) as error:
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

    def _handle_public_media(self, path: str, *, include_body: bool) -> None:
        file_path = resolve_public_media_path(self.settings.media_dir, path)
        if file_path is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            body = file_path.read_bytes()
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if include_body:
            self.wfile.write(body)

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
    if settings.access_protection_incomplete:
        raise RuntimeError("APP_PASSWORD and APP_SESSION_SECRET must be configured together")
    app_server = create_server(host=host, port=port, settings=settings)
    media_server: PublicMediaServer | None = None
    media_thread: threading.Thread | None = None

    if settings.public_media_base_url and settings.media_server_enabled:
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
