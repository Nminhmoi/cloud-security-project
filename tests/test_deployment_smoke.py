import http.cookiejar
import unittest
from email.message import Message

from scripts.smoke_test_deployment import (
    SmokeTestError,
    validate_security_headers,
    validate_session_cookies,
)


class DeploymentSmokeTests(unittest.TestCase):
    def security_headers(self):
        headers = Message()
        headers["Content-Security-Policy"] = "default-src 'self'"
        headers["X-Content-Type-Options"] = "nosniff"
        headers["X-Frame-Options"] = "DENY"
        headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        headers["Permissions-Policy"] = "camera=(), microphone=()"
        headers["Strict-Transport-Security"] = "max-age=31536000"
        return headers

    def test_security_headers_require_hsts_for_https(self):
        headers = self.security_headers()
        validate_security_headers(headers)
        del headers["Strict-Transport-Security"]
        with self.assertRaisesRegex(SmokeTestError, "Strict-Transport-Security"):
            validate_security_headers(headers)
        validate_security_headers(headers, require_https=False)

    def test_session_cookie_requires_secure_and_httponly(self):
        secure_cookie = http.cookiejar.Cookie(
            version=0,
            name="session",
            value="opaque",
            port=None,
            port_specified=False,
            domain="cloudbox.example.com",
            domain_specified=True,
            domain_initial_dot=False,
            path="/",
            path_specified=True,
            secure=True,
            expires=None,
            discard=True,
            comment=None,
            comment_url=None,
            rest={"HttpOnly": None, "SameSite": "Lax"},
            rfc2109=False,
        )
        validate_session_cookies([secure_cookie])
        secure_cookie.secure = False
        with self.assertRaisesRegex(SmokeTestError, "Secure"):
            validate_session_cookies([secure_cookie])

        secure_cookie.secure = True
        secure_cookie._rest.pop("SameSite")
        with self.assertRaisesRegex(SmokeTestError, "SameSite"):
            validate_session_cookies([secure_cookie])

    def test_rejects_missing_session_cookie(self):
        with self.assertRaisesRegex(SmokeTestError, "No Flask session"):
            validate_session_cookies([])


if __name__ == "__main__":
    unittest.main()
