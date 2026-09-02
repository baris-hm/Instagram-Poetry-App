import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from poetry_app.settings import AppSettings


class SettingsTests(unittest.TestCase):
    def test_env_file_enables_publishing_and_normalizes_handle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text(
                "INSTAGRAM_ACCESS_TOKEN=secret-token\n"
                "INSTAGRAM_HANDLE=siirhesabi\n"
                "PUBLIC_MEDIA_BASE_URL=https://media.example.test/\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                settings = AppSettings.from_env(root)

        self.assertTrue(settings.publishing_enabled)
        self.assertEqual(settings.instagram_handle, "@siirhesabi")
        self.assertEqual(settings.public_media_base_url, "https://media.example.test")
        self.assertEqual(settings.media_dir, (root / "instance/media").resolve())

    def test_public_media_url_must_use_https(self) -> None:
        settings = AppSettings(
            instagram_access_token="secret-token",
            public_media_base_url="http://127.0.0.1:8001",
        )

        self.assertFalse(settings.publishing_enabled)
        self.assertIn("PUBLIC_MEDIA_BASE_URL_HTTPS", settings.missing_publish_settings)

    def test_secret_file_overrides_env_token_and_tracks_rotation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            token_file = root / "instagram-token"
            token_file.write_text("first-token\n", encoding="utf-8")
            with patch.dict(
                os.environ,
                {
                    "INSTAGRAM_ACCESS_TOKEN": "stale-env-token",
                    "INSTAGRAM_ACCESS_TOKEN_FILE": str(token_file),
                    "PUBLIC_MEDIA_BASE_URL": "https://media.example.test",
                },
                clear=True,
            ):
                settings = AppSettings.from_env(root)

            self.assertEqual(settings.get_instagram_access_token(), "first-token")
            self.assertTrue(settings.publishing_enabled)

            token_file.write_text("rotated-token", encoding="utf-8")
            self.assertEqual(settings.get_instagram_access_token(), "rotated-token")

    def test_configured_missing_secret_file_disables_publishing(self) -> None:
        settings = AppSettings(
            instagram_access_token="stale-env-token",
            instagram_access_token_file=Path("missing-secret-file"),
            public_media_base_url="https://media.example.test",
        )

        self.assertFalse(settings.publishing_enabled)
        self.assertIn("INSTAGRAM_ACCESS_TOKEN", settings.missing_publish_settings)

    def test_media_only_server_can_be_disabled_for_single_port_hosts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MEDIA_SERVER_ENABLED": "false"}, clear=True):
                settings = AppSettings.from_env(Path(directory))

        self.assertFalse(settings.media_server_enabled)

    def test_hosted_publish_requires_complete_access_protection(self) -> None:
        settings = AppSettings(
            instagram_access_token="token",
            public_media_base_url="https://media.example.test",
            require_auth_for_publish=True,
        )

        self.assertFalse(settings.publishing_enabled)
        self.assertIn("APP_AUTH", settings.missing_publish_settings)

        protected = AppSettings(
            app_password="password",
            app_session_secret="session-secret",
            instagram_access_token="token",
            public_media_base_url="https://media.example.test",
            require_auth_for_publish=True,
        )
        self.assertTrue(protected.publishing_enabled)


if __name__ == "__main__":
    unittest.main()
