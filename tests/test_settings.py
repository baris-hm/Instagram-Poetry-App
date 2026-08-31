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


if __name__ == "__main__":
    unittest.main()
