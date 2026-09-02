import unittest

from poetry_app.auth import create_session_value, is_valid_session_value, session_from_cookie_header


class AuthTests(unittest.TestCase):
    def test_signed_session_is_valid_until_expiry(self) -> None:
        value = create_session_value("secret", 60, now=100)

        self.assertTrue(is_valid_session_value("secret", value, now=159))
        self.assertFalse(is_valid_session_value("secret", value, now=161))

    def test_tampered_or_wrong_secret_session_is_rejected(self) -> None:
        value = create_session_value("secret", 60, now=100)

        self.assertFalse(is_valid_session_value("other", value, now=101))
        self.assertFalse(is_valid_session_value("secret", f"{value}broken", now=101))

    def test_session_cookie_is_extracted_safely(self) -> None:
        self.assertEqual(
            session_from_cookie_header("other=1; poetry_session=123.signature"),
            "123.signature",
        )
        self.assertEqual(session_from_cookie_header("not a cookie"), "")


if __name__ == "__main__":
    unittest.main()
