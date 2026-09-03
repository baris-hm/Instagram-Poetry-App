import json
import tempfile
import threading
import unittest
from io import BytesIO
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image

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
        self.assertIn("Bent görünümü", body)
        self.assertIn("Otomatik", body)
        self.assertIn("7'lik", body)
        self.assertIn("Instagram'da yayınla", body)
        self.assertIn('rel="manifest" href="/manifest.webmanifest"', body)
        self.assertIn("data-install-app", body)

    def test_installable_app_assets_are_served(self) -> None:
        with urlopen(f"{self.base_url}/manifest.webmanifest") as response:
            manifest = json.load(response)
            content_type = response.headers["Content-Type"]

        self.assertEqual(content_type, "application/manifest+json; charset=utf-8")
        self.assertEqual(manifest["name"], "Şiirden Karelere")
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(
            {icon["sizes"] for icon in manifest["icons"]},
            {"192x192", "512x512"},
        )
        self.assertIn(
            "maskable",
            {icon["purpose"] for icon in manifest["icons"]},
        )

        for filename, expected_size in (
            ("icon-64.png", (64, 64)),
            ("icon-192.png", (192, 192)),
            ("icon-512.png", (512, 512)),
            ("icon-maskable-512.png", (512, 512)),
        ):
            with urlopen(f"{self.base_url}/static/icons/{filename}") as response:
                self.assertEqual(response.headers["Content-Type"], "image/png")
                with Image.open(BytesIO(response.read())) as icon:
                    self.assertEqual(icon.size, expected_size)
                    self.assertEqual(icon.mode, "RGB")

    def test_service_worker_never_caches_private_app_data(self) -> None:
        with urlopen(f"{self.base_url}/service-worker.js") as response:
            worker = response.read().decode("utf-8")

        self.assertEqual(response.status, 200)
        self.assertIn('const CACHE_NAME = "siirden-karelere-static-v2"', worker)
        self.assertIn('caches.match("/offline")', worker)
        self.assertNotIn('"/api/', worker)
        self.assertNotIn('"/media/', worker)

        with urlopen(f"{self.base_url}/offline") as response:
            offline_page = response.read().decode("utf-8")
        self.assertIn("İnternet bağlantısı gerekli", offline_page)

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

    def test_render_preview_returns_the_exact_jpeg_used_by_the_renderer(self) -> None:
        long_lines = [
            "Bendeniz tarafından derlenip çevrilmiş ve Ankara’daki Bengü Yayınevi’nde 11 yıl önce, bugünkü tarihte, yayımlanmış olan Bulgar Şiiri Antolojisi Türk okurları tarafından öyle büyük bir ilgi ve sevgiyle karşılanmıştı ki,",
            "Издадената преди 11 години на днешна дата от издателство „Бенгю“ в Анкара беше издадена „Антология на българскака поезия“, съставена и преведена от моя милост.",
        ]

        status, body = self.post_json(
            "/api/render-preview",
            {"slides": [long_lines], "title": "Anı", "description": ""},
        )

        self.assertEqual(status, 200)
        self.assertEqual((body["width"], body["height"]), (1080, 1350))
        self.assertEqual(len(body["preview_urls"]), 1)
        self.assertRegex(body["preview_urls"][0], r"^/media/[a-f0-9]{32}\.jpg$")
        with urlopen(f"{self.base_url}{body['preview_urls'][0]}") as response:
            with Image.open(BytesIO(response.read())) as preview:
                self.assertEqual(preview.size, (1080, 1350))
                self.assertEqual(preview.format, "JPEG")

    def test_preview_defaults_to_automatic_bent_layout_at_37_verses(self) -> None:
        poem = "\n".join(f"Dize {number}" for number in range(1, 38))

        status, body = self.post_json("/api/preview", {"poem": poem, "has_photo": True})

        self.assertEqual(status, 200)
        self.assertEqual(body["layout"], "bent")
        self.assertEqual(body["bent_mode"], "automatic")
        self.assertEqual(body["max_lines_per_slide"], 7)
        self.assertEqual([len(slide) for slide in body["slides"]], [4] * 8 + [5])
        self.assertEqual(body["carousel_slide_count"], 10)

    def test_automatic_bent_layout_balances_44_verses_toward_final_slides(self) -> None:
        poem = "\n".join(f"Dize {number}" for number in range(1, 45))

        status, body = self.post_json(
            "/api/preview",
            {"poem": poem, "layout": "bent", "bent_mode": "automatic"},
        )

        self.assertEqual(status, 200)
        self.assertEqual([len(slide) for slide in body["slides"]], [4] + [5] * 8)

    def test_fixed_bent_layout_uses_requested_size_and_last_remainder(self) -> None:
        poem = "\n".join(f"Dize {number}" for number in range(1, 38))

        status, body = self.post_json(
            "/api/preview",
            {"poem": poem, "layout": "bent", "bent_mode": "5"},
        )

        self.assertEqual(status, 200)
        self.assertEqual(body["bent_mode"], "5")
        self.assertEqual([len(slide) for slide in body["slides"]], [5] * 7 + [2])

    def test_fixed_bent_layout_is_unavailable_above_nine_full_slides(self) -> None:
        poem = "\n".join(f"Dize {number}" for number in range(1, 47))

        status, body = self.post_json(
            "/api/preview",
            {"poem": poem, "layout": "bent", "bent_mode": 5},
        )

        self.assertEqual(status, 400)
        self.assertIn("en fazla 45 dize", body["error"])

    def test_automatic_bent_layout_supports_63_verses(self) -> None:
        poem = "\n".join(f"Dize {number}" for number in range(1, 64))

        status, body = self.post_json(
            "/api/preview",
            {"poem": poem, "layout": "bent", "has_photo": True},
        )

        self.assertEqual(status, 200)
        self.assertEqual([len(slide) for slide in body["slides"]], [7] * 9)
        self.assertEqual(body["carousel_slide_count"], 10)

    def test_preview_rejects_more_than_63_verses(self) -> None:
        poem = "\n".join(f"Dize {number}" for number in range(1, 65))

        status, body = self.post_json("/api/preview", {"poem": poem})

        self.assertEqual(status, 400)
        self.assertIn("en fazla 63 dize", body["error"])

    def test_quatrain_layout_is_unavailable_at_37_verses(self) -> None:
        poem = "\n".join(f"Dize {number}" for number in range(1, 38))

        status, body = self.post_json(
            "/api/preview",
            {"poem": poem, "layout": "quatrain"},
        )

        self.assertEqual(status, 400)
        self.assertIn("Dörtlük görünümü kullanılamaz", body["error"])

    def test_health_endpoint(self) -> None:
        with urlopen(f"{self.base_url}/health") as response:
            body = json.load(response)

        self.assertEqual(response.status, 200)
        self.assertEqual(body, {"status": "ok"})

    def test_public_media_is_served_from_the_main_port(self) -> None:
        filename = f"{'b' * 32}.jpg"
        content = b"jpeg-placeholder"
        (Path(self.temp_dir.name) / filename).write_bytes(content)

        with urlopen(f"{self.base_url}/media/{filename}") as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["Content-Type"], "image/jpeg")
            self.assertEqual(response.read(), content)

        request = Request(f"{self.base_url}/media/{filename}", method="HEAD")
        with urlopen(request) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b"")

        with self.assertRaises(HTTPError) as error:
            urlopen(f"{self.base_url}/media/not-public.jpg")
        self.assertEqual(error.exception.code, 404)

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

    def test_hosted_login_protects_pages_and_apis_but_not_health_or_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            media_dir = Path(directory)
            filename = f"{'c' * 32}.jpg"
            (media_dir / filename).write_bytes(b"public-jpeg")
            server = create_server(
                port=0,
                settings=AppSettings(
                    app_password="family-password",
                    app_session_secret="a-long-random-session-secret",
                    media_dir=media_dir,
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            try:
                connection.request("GET", "/")
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 302)
                self.assertEqual(response.getheader("Location"), "/login")

                for public_app_path in (
                    "/manifest.webmanifest",
                    "/service-worker.js",
                    "/static/icons/icon-192.png",
                ):
                    connection.request("GET", public_app_path)
                    response = connection.getresponse()
                    response.read()
                    self.assertEqual(response.status, 200)

                connection.request("GET", "/health")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.load(response), {"status": "ok"})

                connection.request("GET", f"/media/{filename}")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b"public-jpeg")

                preview = json.dumps({"poem": "Bir dize"}).encode("utf-8")
                connection.request(
                    "POST",
                    "/api/preview",
                    body=preview,
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 401)

                login = urlencode({"password": "family-password"}).encode("utf-8")
                connection.request(
                    "POST",
                    "/login",
                    body=login,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 303)
                session_cookie = response.getheader("Set-Cookie").split(";", maxsplit=1)[0]

                connection.request("GET", "/", headers={"Cookie": session_cookie})
                response = connection.getresponse()
                body = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertIn("Şiiri yapıştır", body)
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
