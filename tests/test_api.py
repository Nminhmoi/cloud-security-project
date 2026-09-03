import io
import os
import sys
import tempfile
import unittest

from werkzeug.security import generate_password_hash

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_ROOT = os.path.join(PROJECT_ROOT, "app")
sys.path.insert(0, APP_ROOT)
_temp_dir = tempfile.TemporaryDirectory()
os.environ["DATABASE_PATH"] = os.path.join(_temp_dir.name, "api-test.db")
os.environ["UPLOAD_FOLDER"] = os.path.join(_temp_dir.name, "uploads")

from app import app  # noqa: E402
from database import get_db_connection  # noqa: E402


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(TESTING=True)

    def setUp(self):
        with app.app_context():
            connection = get_db_connection()
            connection.execute("DELETE FROM document_shares")
            connection.execute("DELETE FROM documents")
            connection.execute("DELETE FROM users")
            password = generate_password_hash("secret123")
            connection.executemany(
                "INSERT INTO users (id, username, email, password, role_id, is_active) VALUES (?, ?, ?, ?, 2, 1)",
                [(1, "owner#1", "owner@test.local", password), (2, "reader#2", "reader@test.local", password)],
            )
            connection.commit()
            connection.close()
        self.client = app.test_client()

    def login(self, username="owner#1"):
        return self.client.post("/api/v1/auth/login", json={"username": username, "password": "secret123"})

    def test_auth_requires_login_and_returns_current_user(self):
        self.assertEqual(self.client.get("/api/v1/me").status_code, 401)
        self.assertEqual(self.login().status_code, 200)
        response = self.client.get("/api/v1/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["username"], "owner#1")

    def test_document_lifecycle_and_sharing(self):
        self.login()
        response = self.client.post(
            "/api/v1/documents",
            data={"file": (io.BytesIO(b"classified"), "report.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 201)
        document_id = response.get_json()["data"]["id"]
        response = self.client.post(
            f"/api/v1/documents/{document_id}/shares", json={"recipient": "reader@test.local"}
        )
        self.assertEqual(response.status_code, 201)
        self.client.post("/api/v1/auth/logout")
        self.login("reader#2")
        shared = self.client.get("/api/v1/documents?view=shared").get_json()["data"]
        self.assertEqual([item["id"] for item in shared], [document_id])
        download = self.client.get(f"/api/v1/documents/{document_id}/download")
        self.assertEqual(download.data, b"classified")
        download.close()
        self.assertEqual(self.client.delete(f"/api/v1/documents/{document_id}").status_code, 404)
        self.client.post("/api/v1/auth/logout")
        self.login()
        self.assertEqual(self.client.delete(f"/api/v1/documents/{document_id}").status_code, 204)
        self.assertEqual(self.client.post(f"/api/v1/documents/{document_id}/restore").status_code, 200)

    def test_favorite_requires_boolean(self):
        self.login()
        response = self.client.patch("/api/v1/documents/1/favorite", json={"is_favorite": 1})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
