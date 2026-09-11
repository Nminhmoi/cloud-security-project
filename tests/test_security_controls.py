import io
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = PROJECT_ROOT / "app"
sys.path.insert(0, str(APP_ROOT))

_bootstrap_directory = tempfile.TemporaryDirectory()
os.environ["DATABASE_PATH"] = str(Path(_bootstrap_directory.name) / "bootstrap.db")
os.environ["UPLOAD_FOLDER"] = str(Path(_bootstrap_directory.name) / "uploads")
os.environ["WTF_CSRF_ENABLED"] = "false"
os.environ["RATELIMIT_ENABLED"] = "false"

from app import app as bootstrap_app, create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from models import ActivityLog, PasswordResetOTP, User  # noqa: E402
from services.email_service import EmailDeliveryError  # noqa: E402
from services.auth_service import complete_password_reset  # noqa: E402


class SecurityControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(cls.temporary_directory.name) / "security.db"

        class SecurityTestConfig(Config):
            TESTING = True
            SECRET_KEY = "security-controls-test-secret"
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{database_path.as_posix()}"
            SQLALCHEMY_ENGINE_OPTIONS = {}
            AUTO_CREATE_SCHEMA = True
            UPLOAD_FOLDER = str(Path(cls.temporary_directory.name) / "uploads")
            WTF_CSRF_ENABLED = True
            RATELIMIT_ENABLED = True
            RATELIMIT_STORAGE_URI = "memory://"
            MAX_CONTENT_LENGTH = 1024
            MAX_FAILED_LOGIN_ATTEMPTS = 3
            ACCOUNT_LOCK_MINUTES = 15
            MIN_PASSWORD_LENGTH = 12

        cls.app = create_app(SecurityTestConfig)

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        cls.temporary_directory.cleanup()
        with bootstrap_app.app_context():
            db.session.remove()
            db.engine.dispose()
        _bootstrap_directory.cleanup()

    def setUp(self):
        with self.app.app_context():
            db.session.query(ActivityLog).delete()
            db.session.query(User).delete()
            db.session.add(
                User(
                    id=1,
                    username="secure#1",
                    email="secure@example.test",
                    password=generate_password_hash("Correct Horse Battery Staple!"),
                    role_id=2,
                )
            )
            db.session.commit()
        self.client = self.app.test_client()
        test_names = sorted(
            name for name in dir(type(self)) if name.startswith("test_")
        )
        self.remote_address = f"192.0.2.{test_names.index(self._testMethodName) + 1}"

    def request(self, method, path, **kwargs):
        overrides = kwargs.pop("environ_overrides", {})
        overrides["REMOTE_ADDR"] = self.remote_address
        return self.client.open(
            path,
            method=method,
            environ_overrides=overrides,
            **kwargs,
        )

    def csrf_token(self):
        response = self.request("GET", "/api/v1/csrf-token")
        return response.get_json()["data"]["csrf_token"]

    def csrf_headers(self):
        return {"X-CSRFToken": self.csrf_token()}

    def login(self):
        return self.request(
            "POST",
            "/api/v1/auth/login",
            json={
                "username": "secure#1",
                "password": "Correct Horse Battery Staple!",
            },
            headers=self.csrf_headers(),
        )

    def test_csrf_rejects_missing_token_and_accepts_header(self):
        rejected = self.request(
            "POST",
            "/api/v1/auth/login",
            json={"username": "secure#1", "password": "wrong"},
        )
        accepted = self.login()

        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(accepted.status_code, 200)

    def test_security_headers_and_nonce_are_present(self):
        response = self.request("GET", "/login")
        content_security_policy = response.headers["Content-Security-Policy"]
        html = response.get_data(as_text=True)

        nonce = re.search(r"script-src 'self' 'nonce-([^']+)'", content_security_policy)
        self.assertIsNotNone(nonce)
        self.assertIn(f'nonce="{nonce.group(1)}"', html)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn("camera=()", response.headers["Permissions-Policy"])
        self.assertIn('name="csrf_token"', html)

        secure_response = self.request(
            "GET",
            "/login",
            environ_overrides={"HTTP_X_FORWARDED_PROTO": "https"},
        )
        self.assertIn("max-age=31536000", secure_response.headers["Strict-Transport-Security"])

    def test_login_lockout_records_audit_events(self):
        headers = self.csrf_headers()
        for _ in range(3):
            response = self.request(
                "POST",
                "/api/v1/auth/login",
                json={"username": "secure#1", "password": "wrong-password"},
                headers=headers,
            )
            self.assertEqual(response.status_code, 401)

        locked = self.request(
            "POST",
            "/api/v1/auth/login",
            json={
                "username": "secure#1",
                "password": "Correct Horse Battery Staple!",
            },
            headers=headers,
        )
        self.assertEqual(locked.status_code, 429)

        with self.app.app_context():
            user = db.session.get(User, 1)
            self.assertEqual(user.failed_login_attempts, 3)
            self.assertIsNotNone(user.locked_until)
            self.assertEqual(
                db.session.query(ActivityLog)
                .filter(ActivityLog.action == "login_failed")
                .count(),
                3,
            )

    def test_login_endpoint_is_rate_limited(self):
        headers = self.csrf_headers()
        for _ in range(5):
            response = self.request(
                "POST",
                "/api/v1/auth/login",
                json={"username": "unknown#1", "password": "wrong-password"},
                headers=headers,
            )
            self.assertEqual(response.status_code, 401)

        limited = self.request(
            "POST",
            "/api/v1/auth/login",
            json={"username": "unknown#1", "password": "wrong-password"},
            headers=headers,
        )
        self.assertEqual(limited.status_code, 429)

    def test_upload_rejects_dangerous_and_oversized_files(self):
        self.assertEqual(self.login().status_code, 200)
        headers = self.csrf_headers()

        dangerous = self.request(
            "POST",
            "/api/v1/documents",
            data={"file": (io.BytesIO(b"binary"), "malware.exe")},
            content_type="multipart/form-data",
            headers=headers,
        )
        disguised = self.request(
            "POST",
            "/api/v1/documents",
            data={"file": (io.BytesIO(b"not a PDF"), "fake.pdf")},
            content_type="multipart/form-data",
            headers=headers,
        )
        accepted = self.request(
            "POST",
            "/api/v1/documents",
            data={"file": (io.BytesIO(b"safe text"), "notes.txt")},
            content_type="multipart/form-data",
            headers=headers,
        )
        oversized = self.request(
            "POST",
            "/api/v1/documents",
            data={"file": (io.BytesIO(b"x" * 2048), "large.txt")},
            content_type="multipart/form-data",
            headers=headers,
        )

        self.assertEqual(dangerous.status_code, 400)
        self.assertEqual(disguised.status_code, 400)
        self.assertEqual(accepted.status_code, 201)
        self.assertEqual(oversized.status_code, 413)

    def test_password_policy_and_post_only_logout(self):
        headers = self.csrf_headers()
        short_password = self.request(
            "POST",
            "/api/v1/auth/register",
            json={
                "username": "newuser#1",
                "email": "new@example.test",
                "password": "too-short",
            },
            headers=headers,
        )

        self.assertEqual(short_password.status_code, 400)
        self.assertEqual(self.request("GET", "/logout").status_code, 405)

    def test_password_reset_invalidates_existing_session(self):
        self.assertEqual(self.login().status_code, 200)
        with self.app.app_context():
            complete_password_reset(
                db.session.get(User, 1),
                "Another Correct Horse Password!",
            )

        response = self.request("GET", "/documents")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/login"))

    @patch(
        "routes.auth.send_otp_email",
        side_effect=EmailDeliveryError("SES unavailable"),
    )
    def test_failed_otp_delivery_removes_code_and_hides_account_state(self, _send):
        response = self.request(
            "POST",
            "/forgot-password",
            data={"email": "secure@example.test"},
            headers=self.csrf_headers(),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/verify-otp"))
        with self.client.session_transaction() as browser_session:
            self.assertEqual(browser_session["reset_user_id"], -1)
        with self.app.app_context():
            self.assertIsNone(db.session.get(PasswordResetOTP, 1))


if __name__ == "__main__":
    unittest.main()
