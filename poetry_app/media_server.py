"""A separate, read-only server for media that Instagram needs to fetch."""

from __future__ import annotations

import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_MEDIA_PATH = re.compile(r"^/media/([a-f0-9]{32}\.jpg)$")


class PublicMediaRequestHandler(BaseHTTPRequestHandler):
    server_version = "PoetryMedia/0.1"

    def do_GET(self) -> None:  # noqa: N802
        self._serve(include_body=True)

    def do_HEAD(self) -> None:  # noqa: N802
        self._serve(include_body=False)

    def _serve(self, *, include_body: bool) -> None:
        path = self.path.split("?", maxsplit=1)[0]
        match = _MEDIA_PATH.fullmatch(path)
        if match is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        file_path = self.server.media_dir / match.group(1)  # type: ignore[attr-defined]
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

    def log_message(self, format: str, *args: object) -> None:
        return


class PublicMediaServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], media_dir: Path) -> None:
        self.media_dir = media_dir
        self.media_dir.mkdir(parents=True, exist_ok=True)
        super().__init__(address, PublicMediaRequestHandler)


def create_media_server(
    media_dir: Path,
    host: str = "127.0.0.1",
    port: int = 8001,
) -> PublicMediaServer:
    return PublicMediaServer((host, port), media_dir)

