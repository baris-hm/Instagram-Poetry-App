import unittest
from urllib.parse import parse_qs, urlsplit

from poetry_app.instagram_client import InstagramAPIError, InstagramClient


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str], dict[str, list[str]]]] = []
        self.child_count = 0

    def __call__(self, method, url, headers, body, timeout):
        form = parse_qs(body.decode("utf-8")) if body else {}
        self.calls.append((method, url, headers, form))
        path = urlsplit(url).path

        if method == "GET" and path.endswith("/me"):
            return {"user_id": "ig-user", "username": "siirhesabi"}
        if method == "POST" and path.endswith("/ig-user/media"):
            if form.get("media_type") == ["CAROUSEL"]:
                return {"id": "carousel"}
            self.child_count += 1
            return {"id": f"child-{self.child_count}"}
        if method == "GET" and any(path.endswith(suffix) for suffix in ("/child-1", "/child-2", "/carousel")):
            return {"status_code": "FINISHED"}
        if method == "POST" and path.endswith("/ig-user/media_publish"):
            return {"id": "published-media"}
        if method == "GET" and path.endswith("/published-media"):
            return {"permalink": "https://www.instagram.com/p/example/"}
        raise AssertionError(f"Unexpected request: {method} {url} {form}")


class InstagramClientTests(unittest.TestCase):
    def test_publishes_single_image_without_carousel_parent(self) -> None:
        transport = FakeTransport()
        client = InstagramClient(
            "top-secret",
            transport=transport,
            sleep=lambda _: None,
        )

        post = client.publish_images(
            ["https://media.example.test/a.jpg"],
            caption="Tek kare",
        )

        self.assertEqual(post.media_id, "published-media")
        image_call = next(
            call
            for call in transport.calls
            if call[0] == "POST" and call[1].endswith("/ig-user/media")
        )
        self.assertEqual(image_call[3]["caption"], ["Tek kare"])
        self.assertNotIn("is_carousel_item", image_call[3])
        self.assertFalse(
            any(call[3].get("media_type") == ["CAROUSEL"] for call in transport.calls)
        )

    def test_publishes_two_image_carousel_with_bearer_token(self) -> None:
        transport = FakeTransport()
        client = InstagramClient(
            "top-secret",
            transport=transport,
            sleep=lambda _: None,
        )

        post = client.publish_images(
            ["https://media.example.test/a.jpg", "https://media.example.test/b.jpg"],
            caption="Bir açıklama",
        )

        self.assertEqual(post.media_id, "published-media")
        self.assertEqual(post.permalink, "https://www.instagram.com/p/example/")
        parent_call = next(
            call for call in transport.calls if call[3].get("media_type") == ["CAROUSEL"]
        )
        self.assertEqual(parent_call[3]["children"], ["child-1,child-2"])
        self.assertEqual(parent_call[3]["caption"], ["Bir açıklama"])
        self.assertEqual(parent_call[2]["Authorization"], "Bearer top-secret")
        self.assertNotIn("top-secret", parent_call[1])
        self.assertEqual(parent_call[2]["Content-Type"], "application/x-www-form-urlencoded")

    def test_reports_the_carousel_item_and_processing_stage(self) -> None:
        class FailingTransport(FakeTransport):
            def __call__(self, method, url, headers, body, timeout):
                if method == "GET" and urlsplit(url).path.endswith("/child-1"):
                    raise InstagramAPIError(
                        "Only photo or video can be accepted as media type. (kod 9004, alt kod 2207052)"
                    )
                return super().__call__(method, url, headers, body, timeout)

        client = InstagramClient("top-secret", transport=FailingTransport(), sleep=lambda _: None)

        with self.assertRaisesRegex(
            InstagramAPIError,
            r"Karuselin 1\. karesi işlenirken: Only photo or video",
        ):
            client.publish_images(
                ["https://media.example.test/a.jpg", "https://media.example.test/b.jpg"]
            )


if __name__ == "__main__":
    unittest.main()
