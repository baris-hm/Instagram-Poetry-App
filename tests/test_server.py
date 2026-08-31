import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from poetry_app.server import create_server
from poetry_app.settings import AppSettings


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.server = create_server(
            port=0,
            settings=AppSettings(media_dir=Path(cls.temp_dir.name)),
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temp_dir.cleanup()

    def post_json(self, path: str, payload: dict) -> tuple[int, dict]:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_home_page_is_served(self) -> None:
        with urlopen(f"{self.base_url}/") as response:
            body = response.read().decode("utf-8")

        self.assertEqual(response.status, 200)
        self.assertIn("Şiiri yapıştır", body)
        self.assertIn("Dörtlük görünümü", body)
        self.assertIn("Beyit görünümü", body)
        self.assertIn("Instagram'da yayınla", body)

    def test_preview_route_supports_refresh(self) -> None:
        with urlopen(f"{self.base_url}/preview") as response:
            body = response.read().decode("utf-8")

        self.assertEqual(response.status, 200)
        self.assertIn("id=\"preview-view\"", body)

    def test_preview_api_returns_divided_slides(self) -> None:
        status, body = self.post_json(
            "/api/preview",
            {
                "poem": "Bir\nİki\nÜç\nDört\nBeş",
                "title": "Deneme",
                "description": "Bir açıklama",
            },
        )

        self.assertEqual(status, 200)
        self.assertEqual(body["title"], "Deneme")
        self.assertEqual(body["lines_per_slide"], 4)
        self.assertEqual(body["max_lines_per_slide"], 4)
        self.assertEqual(body["slides"], [["Bir", "İki", "Üç", "Dört"], ["Beş"]])

    def test_preview_api_supports_couplet_layout(self) -> None:
        status, body = self.post_json(
            "/api/preview",
            {"poem": "Bir\nİki\nÜç\nDört\nBeş", "lines_per_slide": 2},
        )

        self.assertEqual(status, 200)
        self.assertEqual(body["lines_per_slide"], 2)
        self.assertEqual(body["max_lines_per_slide"], 4)
        self.assertEqual(body["slides"], [["Bir", "İki"], ["Üç", "Dört"], ["Beş"]])

    def test_couplet_layout_counts_optional_photo_against_limit(self) -> None:
        poem = "\n".join(f"Dize {number}" for number in range(1, 20))

        status, body = self.post_json(
            "/api/preview",
            {"poem": poem, "lines_per_slide": 2, "has_photo": True},
        )

        self.assertEqual(status, 400)
        self.assertIn("en fazla 10 kare", body["error"])

    def test_preview_api_rejects_unsupported_layout(self) -> None:
        status, body = self.post_json(
            "/api/preview",
            {"poem": "Bir\nİki", "lines_per_slide": 3},
        )

        self.assertEqual(status, 400)
        self.assertIn("iki veya dört", body["error"])

    def test_preview_api_rejects_an_empty_poem(self) -> None:
        status, body = self.post_json("/api/preview", {"poem": "   "})

        self.assertEqual(status, 400)
        self.assertIn("şiirinizi", body["error"])

    def test_health_endpoint(self) -> None:
        with urlopen(f"{self.base_url}/health") as response:
            body = json.load(response)

        self.assertEqual(response.status, 200)
        self.assertEqual(body, {"status": "ok"})

    def test_config_endpoint_reports_publish_setup(self) -> None:
        with urlopen(f"{self.base_url}/api/config") as response:
            body = json.load(response)

        self.assertEqual(response.status, 200)
        self.assertFalse(body["publishing_enabled"])
        self.assertEqual(body["instagram_handle"], "@handle-")
        self.assertIn("INSTAGRAM_ACCESS_TOKEN", body["missing"])

    def test_publish_endpoint_is_disabled_without_secrets(self) -> None:
        status, body = self.post_json(
            "/api/publish",
            {"slides": [["Bir dize"]], "title": "", "description": ""},
        )

        self.assertEqual(status, 503)
        self.assertIn(".env", body["error"])


if __name__ == "__main__":
    unittest.main()
