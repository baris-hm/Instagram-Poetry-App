"""Environment-backed configuration for publishing and media hosting."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path) -> None:
    """Load a small, conventional ``.env`` file without another dependency."""

    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        if key:
            os.environ.setdefault(key, value)


@dataclass(frozen=True, slots=True)
class AppSettings:
    instagram_access_token: str = ""
    instagram_user_id: str = ""
    instagram_handle: str = "@handle-"
    graph_api_version: str = "v26.0"
    graph_api_base_url: str = "https://graph.instagram.com"
    public_media_base_url: str = ""
    media_dir: Path = Path("instance/media")
    media_host: str = "127.0.0.1"
    media_port: int = 8001

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> "AppSettings":
        root = (project_root or Path.cwd()).resolve()
        load_dotenv(root / ".env")
        media_dir = Path(os.getenv("MEDIA_DIR", "instance/media"))
        if not media_dir.is_absolute():
            media_dir = root / media_dir

        handle = os.getenv("INSTAGRAM_HANDLE", "@handle-").strip()
        if handle and not handle.startswith("@"):
            handle = f"@{handle}"

        return cls(
            instagram_access_token=os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip(),
            instagram_user_id=os.getenv("INSTAGRAM_USER_ID", "").strip(),
            instagram_handle=handle or "@handle-",
            graph_api_version=os.getenv("INSTAGRAM_GRAPH_API_VERSION", "v26.0").strip(),
            graph_api_base_url=os.getenv(
                "INSTAGRAM_GRAPH_BASE_URL",
                "https://graph.instagram.com",
            ).strip().rstrip("/"),
            public_media_base_url=os.getenv("PUBLIC_MEDIA_BASE_URL", "").strip().rstrip("/"),
            media_dir=media_dir.resolve(),
            media_host=os.getenv("MEDIA_HOST", "127.0.0.1").strip(),
            media_port=int(os.getenv("MEDIA_PORT", "8001")),
        )

    @property
    def publishing_enabled(self) -> bool:
        return not self.missing_publish_settings

    @property
    def missing_publish_settings(self) -> tuple[str, ...]:
        missing: list[str] = []
        if not self.instagram_access_token:
            missing.append("INSTAGRAM_ACCESS_TOKEN")
        if not self.public_media_base_url:
            missing.append("PUBLIC_MEDIA_BASE_URL")
        elif not self.public_media_base_url.startswith("https://"):
            missing.append("PUBLIC_MEDIA_BASE_URL_HTTPS")
        return tuple(missing)

