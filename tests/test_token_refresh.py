import unittest
from urllib.parse import parse_qs, urlsplit

from poetry_app.token_refresh import (
    TokenRefreshError,
    refresh_long_lived_token,
    refresh_validate_and_store,
)


class FakeRefreshTransport:
    def __init__(self) -> None:
        self.calls = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append((method, url, headers, body, timeout))
        split = urlsplit(url)
        if split.path == "/refresh_access_token":
            query = parse_qs(split.query)
            if query.get("grant_type") != ["ig_refresh_token"]:
                raise AssertionError("Missing refresh grant type")
            if query.get("access_token") != ["old-token"]:
                raise AssertionError("Missing source token")
            return {
                "access_token": "rotated-token",
                "token_type": "bearer",
                "expires_in": 5_184_000,
            }
        if split.path.endswith("/v26.0/me"):
            if headers.get("Authorization") != "Bearer rotated-token":
                raise AssertionError("Refreshed token was not validated")
            return {"user_id": "ig-user", "username": "siirhesabi"}
        raise AssertionError(f"Unexpected request: {method} {url}")


class TokenRefreshTests(unittest.TestCase):
    def test_refreshes_validates_and_stores_replacement_token(self) -> None:
        transport = FakeRefreshTransport()
        stored = []

        result = refresh_validate_and_store(
            "old-token",
            "projects/test-project/secrets/instagram-access-token",
            transport=transport,
            secret_writer=lambda resource, payload: stored.append((resource, payload)) or "7",
        )

        self.assertEqual(result.username, "siirhesabi")
        self.assertEqual(result.secret_version, "7")
        self.assertEqual(result.expires_in, 5_184_000)
        self.assertEqual(
            stored,
            [
                (
                    "projects/test-project/secrets/instagram-access-token",
                    b"rotated-token",
                )
            ],
        )

    def test_rejects_refresh_response_without_token(self) -> None:
        def transport(method, url, headers, body, timeout):
            return {"expires_in": 5_184_000}

        with self.assertRaisesRegex(TokenRefreshError, "did not return a refreshed"):
            refresh_long_lived_token("old-token", transport=transport)

    def test_rejects_invalid_secret_resource_before_calling_meta(self) -> None:
        with self.assertRaisesRegex(TokenRefreshError, "SECRET_RESOURCE"):
            refresh_validate_and_store(
                "old-token",
                "instagram-access-token",
                transport=lambda *args: self.fail("Meta should not be called"),
            )


if __name__ == "__main__":
    unittest.main()
