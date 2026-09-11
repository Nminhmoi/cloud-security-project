import io
import hashlib
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_ROOT = os.path.join(PROJECT_ROOT, "app")
sys.path.insert(0, APP_ROOT)
_temp_dir = tempfile.TemporaryDirectory()
os.environ["DATABASE_PATH"] = os.path.join(_temp_dir.name, "api-test.db")
os.environ["UPLOAD_FOLDER"] = os.path.join(_temp_dir.name, "uploads")
os.environ["WTF_CSRF_ENABLED"] = "false"
os.environ["RATELIMIT_ENABLED"] = "false"
os.environ["MIN_PASSWORD_LENGTH"] = "8"

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
            connection.execute("DELETE FROM activity_logs")
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

    def upload(self, filename="report.txt", content=b"classified"):
        return self.client.post(
            "/api/v1/documents",
            data={"file": (io.BytesIO(content), filename)},
            content_type="multipart/form-data",
        )

    def test_registration_validates_input_and_rejects_duplicates(self):
        invalid_username = self.client.post(
            "/api/v1/auth/register",
            json={"username": "plain", "email": "new@test.local", "password": "secret123"},
        )
        invalid_email = self.client.post(
            "/api/v1/auth/register",
            json={"username": "new#123", "email": "invalid", "password": "secret123"},
        )
        short_password = self.client.post(
            "/api/v1/auth/register",
            json={"username": "new#123", "email": "new@test.local", "password": "12345"},
        )
        created = self.client.post(
            "/api/v1/auth/register",
            json={"username": "new#123", "email": "NEW@test.local", "password": "secret123"},
        )
        duplicate = self.client.post(
            "/api/v1/auth/register",
            json={"username": "new#123", "email": "other@test.local", "password": "secret123"},
        )

        self.assertEqual(invalid_username.status_code, 400)
        self.assertEqual(invalid_email.status_code, 400)
        self.assertEqual(short_password.status_code, 400)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json()["data"]["email"], "new@test.local")
        self.assertEqual(duplicate.status_code, 409)
        with app.app_context():
            connection = get_db_connection()
            user = connection.execute(
                "SELECT password FROM users WHERE username = 'new#123'"
            ).fetchone()
            connection.close()
        self.assertNotEqual(user["password"], "secret123")

    def test_login_logout_and_inactive_account(self):
        bad_login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "owner#1", "password": "wrong-password"},
        )
        self.assertEqual(bad_login.status_code, 401)

        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.client.post("/api/v1/auth/logout").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/me").status_code, 401)

        with app.app_context():
            connection = get_db_connection()
            connection.execute("UPDATE users SET is_active = 0 WHERE id = 1")
            connection.commit()
            connection.close()
        self.assertEqual(self.login().status_code, 403)

    def test_auth_requires_login_and_returns_current_user(self):
        self.assertEqual(self.client.get("/api/v1/me").status_code, 401)
        self.assertEqual(self.login().status_code, 200)
        response = self.client.get("/api/v1/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["username"], "owner#1")

    def test_document_lifecycle_and_sharing(self):
        self.login()
        response = self.upload()
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

    def test_document_views_favorite_and_owner_boundaries(self):
        self.login()
        first_id = self.upload("first.txt", b"one").get_json()["data"]["id"]
        second_id = self.upload("second.txt", b"two").get_json()["data"]["id"]

        favorite = self.client.patch(
            f"/api/v1/documents/{first_id}/favorite", json={"is_favorite": True}
        )
        self.assertEqual(favorite.status_code, 200)
        mine = self.client.get("/api/v1/documents?view=mine")
        self.assertEqual(mine.status_code, 200)
        by_id = {item["id"]: item for item in mine.get_json()["data"]}
        self.assertTrue(by_id[first_id]["is_favorite"])

        self.assertEqual(self.client.delete(f"/api/v1/documents/{second_id}").status_code, 204)
        deleted = self.client.get("/api/v1/documents?view=deleted").get_json()["data"]
        self.assertEqual([item["id"] for item in deleted], [second_id])
        self.assertEqual(self.client.get("/api/v1/documents?view=invalid").status_code, 400)
        self.assertEqual(self.client.patch(
            f"/api/v1/documents/{second_id}/favorite", json={"is_favorite": True}
        ).status_code, 404)

        self.client.post("/api/v1/auth/logout")
        self.login("reader#2")
        self.assertEqual(self.client.delete(f"/api/v1/documents/{first_id}").status_code, 404)
        self.assertEqual(self.client.post(f"/api/v1/documents/{second_id}/restore").status_code, 404)

    def test_upload_requires_authentication_and_file(self):
        self.assertEqual(self.upload().status_code, 401)
        self.login()
        response = self.client.post(
            "/api/v1/documents", data={}, content_type="multipart/form-data"
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_persists_safe_metadata_and_unique_storage_keys(self):
        self.login()
        first = self.upload("same-name.txt", b"same-content")
        second = self.upload("same-name.txt", b"same-content")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        first_data = first.get_json()["data"]
        second_data = second.get_json()["data"]
        self.assertEqual(first_data["filename"], "same-name.txt")
        self.assertEqual(first_data["content_type"], "text/plain")
        self.assertEqual(
            first_data["sha256"], hashlib.sha256(b"same-content").hexdigest()
        )
        self.assertEqual(first_data["sha256"], second_data["sha256"])

        with app.app_context():
            connection = get_db_connection()
            keys = connection.execute(
                "SELECT storage_key FROM documents ORDER BY id"
            ).fetchall()
            connection.close()
        self.assertEqual(len({row["storage_key"] for row in keys}), 2)
        self.assertTrue(all(row["storage_key"].startswith("1/") for row in keys))

    def test_upload_enforces_user_quota(self):
        original_quota = app.config["USER_STORAGE_QUOTA_BYTES"]
        app.config["USER_STORAGE_QUOTA_BYTES"] = 5
        try:
            self.login()
            response = self.upload("quota.txt", b"123456")
            self.assertEqual(response.status_code, 413)
            with app.app_context():
                connection = get_db_connection()
                count = connection.execute(
                    "SELECT COUNT(*) AS count FROM documents"
                ).fetchone()["count"]
                connection.close()
            self.assertEqual(count, 0)
        finally:
            app.config["USER_STORAGE_QUOTA_BYTES"] = original_quota

    def test_database_failure_removes_orphaned_upload(self):
        self.login()

        def stored_files():
            return {
                os.path.join(root, filename)
                for root, _directories, filenames in os.walk(app.config["UPLOAD_FOLDER"])
                for filename in filenames
            }

        before = stored_files()
        with patch(
            "services.document_service.db.session.commit",
            side_effect=RuntimeError("database unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                self.upload("orphan.txt", b"orphan")
        self.assertEqual(stored_files(), before)

    def test_revoked_create_permission_blocks_api_upload(self):
        with app.app_context():
            connection = get_db_connection()
            connection.execute(
                "DELETE FROM role_permissions WHERE role_id = 2 AND permission_id = 2"
            )
            connection.commit()
            connection.close()
        try:
            self.login()
            response = self.upload("blocked.txt", b"blocked")
            self.assertEqual(response.status_code, 403)
        finally:
            with app.app_context():
                connection = get_db_connection()
                connection.execute(
                    "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (2, 2)"
                )
                connection.commit()
                connection.close()

    def test_soft_delete_records_timestamp_and_restore_clears_it(self):
        self.login()
        document_id = self.upload("trash.txt", b"trash").get_json()["data"]["id"]
        self.assertEqual(
            self.client.delete(f"/api/v1/documents/{document_id}").status_code,
            204,
        )
        with app.app_context():
            connection = get_db_connection()
            deleted_at = connection.execute(
                "SELECT deleted_at FROM documents WHERE id = ?", (document_id,)
            ).fetchone()["deleted_at"]
            connection.close()
        self.assertIsNotNone(deleted_at)

        self.assertEqual(
            self.client.post(f"/api/v1/documents/{document_id}/restore").status_code,
            200,
        )
        with app.app_context():
            connection = get_db_connection()
            deleted_at = connection.execute(
                "SELECT deleted_at FROM documents WHERE id = ?", (document_id,)
            ).fetchone()["deleted_at"]
            connection.close()
        self.assertIsNone(deleted_at)

    def test_download_blocks_pending_and_infected_scan_status(self):
        self.login()
        document_id = self.upload("scan.txt", b"scan-me").get_json()["data"]["id"]
        with app.app_context():
            connection = get_db_connection()
            connection.execute(
                "UPDATE documents SET scan_status = 'pending' WHERE id = ?",
                (document_id,),
            )
            connection.commit()
            connection.close()
        self.assertEqual(
            self.client.get(f"/api/v1/documents/{document_id}/download").status_code,
            423,
        )

        with app.app_context():
            connection = get_db_connection()
            connection.execute(
                "UPDATE documents SET scan_status = 'infected' WHERE id = ?",
                (document_id,),
            )
            connection.commit()
            connection.close()
        self.assertEqual(
            self.client.get(f"/api/v1/documents/{document_id}/download").status_code,
            403,
        )

    def test_purge_command_removes_expired_trash_and_file(self):
        self.login()
        document_id = self.upload("expired.txt", b"expired").get_json()["data"]["id"]
        self.assertEqual(
            self.client.delete(f"/api/v1/documents/{document_id}").status_code,
            204,
        )
        with app.app_context():
            connection = get_db_connection()
            storage_key = connection.execute(
                "SELECT storage_key FROM documents WHERE id = ?", (document_id,)
            ).fetchone()["storage_key"]
            connection.close()
        path = os.path.join(app.config["UPLOAD_FOLDER"], *storage_key.split("/"))
        self.assertTrue(os.path.isfile(path))

        result = app.test_cli_runner().invoke(
            args=["purge-deleted-documents", "--retention-days", "0"]
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Purged 1", result.output)
        self.assertFalse(os.path.exists(path))
        with app.app_context():
            connection = get_db_connection()
            row = connection.execute(
                "SELECT 1 FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
            connection.close()
        self.assertIsNone(row)

    def test_user_search_validation_and_visibility(self):
        self.login()
        self.assertEqual(self.client.get("/api/v1/users/search?q=r").status_code, 400)
        response = self.client.get("/api/v1/users/search?q=reader")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([user["username"] for user in response.get_json()["data"]], ["reader#2"])

        with app.app_context():
            connection = get_db_connection()
            connection.execute("UPDATE users SET is_active = 0 WHERE id = 2")
            connection.commit()
            connection.close()
        response = self.client.get("/api/v1/users/search?q=reader")
        self.assertEqual(response.get_json()["data"], [])

    def test_share_lifecycle_validation_and_authorization(self):
        self.login()
        document_id = self.upload().get_json()["data"]["id"]

        self.assertEqual(
            self.client.post(f"/api/v1/documents/{document_id}/shares", json={}).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/documents/{document_id}/shares", json={"recipient": "owner#1"}
            ).status_code,
            400,
        )
        created = self.client.post(
            f"/api/v1/documents/{document_id}/shares", json={"recipient": "READER@test.local"}
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(
            self.client.post(
                f"/api/v1/documents/{document_id}/shares", json={"recipient": "reader#2"}
            ).status_code,
            409,
        )
        shares = self.client.get(f"/api/v1/documents/{document_id}/shares")
        self.assertEqual([user["id"] for user in shares.get_json()["data"]], [2])

        self.client.post("/api/v1/auth/logout")
        self.login("reader#2")
        self.assertEqual(self.client.get(f"/api/v1/documents/{document_id}/shares").status_code, 404)
        self.assertEqual(
            self.client.delete(f"/api/v1/documents/{document_id}/shares/2").status_code,
            404,
        )
        download = self.client.get(f"/api/v1/documents/{document_id}/download")
        self.assertEqual(download.status_code, 200)
        download.close()

        self.client.post("/api/v1/auth/logout")
        self.login()
        self.assertEqual(
            self.client.delete(f"/api/v1/documents/{document_id}/shares/2").status_code,
            204,
        )
        self.client.post("/api/v1/auth/logout")
        self.login("reader#2")
        self.assertEqual(self.client.get(f"/api/v1/documents/{document_id}/download").status_code, 404)


if __name__ == "__main__":
    unittest.main()
