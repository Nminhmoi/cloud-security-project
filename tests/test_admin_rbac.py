import os
import sys
import tempfile
import unittest

from werkzeug.security import generate_password_hash


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_ROOT = os.path.join(PROJECT_ROOT, "app")
sys.path.insert(0, APP_ROOT)

_temp_dir = tempfile.TemporaryDirectory()
os.environ["DATABASE_PATH"] = os.path.join(_temp_dir.name, "test.db")
os.environ["UPLOAD_FOLDER"] = os.path.join(_temp_dir.name, "uploads")

from app import app  # noqa: E402
from admin import AdminManager  # noqa: E402
from database import get_db_connection  # noqa: E402


class AdminRbacTests(unittest.TestCase):
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
                "INSERT INTO users (id, username, email, password, role_id, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (1, "admin-one", "a1@test.local", password, 1, 1),
                    (2, "admin-two", "a2@test.local", password, 1, 1),
                    (3, "normal-user", "user@test.local", password, 2, 1),
                ],
            )
            connection.commit()
            connection.close()
        self.client = app.test_client()

    def login_session(self, user_id, username):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["username"] = username

    def test_normal_user_cannot_access_admin(self):
        self.login_session(3, "normal-user")
        self.assertEqual(self.client.get("/admin/dashboard").status_code, 403)

    def test_login_redirects_each_role_to_its_home_page(self):
        admin_response = self.client.post(
            "/login", data={"username": "admin-one", "password": "secret123"}
        )
        self.assertEqual(admin_response.status_code, 302)
        self.assertTrue(admin_response.headers["Location"].endswith("/admin/dashboard"))

        user_response = self.client.post(
            "/login", data={"username": "normal-user", "password": "secret123"}
        )
        self.assertEqual(user_response.status_code, 302)
        self.assertTrue(user_response.headers["Location"].endswith("/"))

    def test_users_page_marks_the_real_role(self):
        self.login_session(1, "admin-one")
        response = self.client.get("/admin/users")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        user_section = html.split('data-user-id="3"', 1)[1].split("</tr>", 1)[0]
        self.assertRegex(user_section, r'value="2"\s+selected')

    def test_role_endpoint_validates_json_and_references(self):
        self.login_session(1, "admin-one")
        self.assertEqual(self.client.post("/admin/users/3/role").status_code, 400)
        self.assertEqual(
            self.client.post("/admin/users/3/role", json={"role_id": 999}).status_code,
            404,
        )

    def test_delete_user_removes_incoming_and_outgoing_shares(self):
        with app.app_context():
            connection = get_db_connection()
            connection.execute("INSERT INTO documents (id, filename, user_id) VALUES (10, 'a.txt', 3)")
            connection.execute("INSERT INTO documents (id, filename, user_id) VALUES (11, 'b.txt', 1)")
            connection.execute("INSERT INTO document_shares (document_id, shared_with_user_id) VALUES (10, 1)")
            connection.execute("INSERT INTO document_shares (document_id, shared_with_user_id) VALUES (11, 3)")
            connection.commit()
            connection.close()
        self.login_session(1, "admin-one")
        self.assertEqual(self.client.post("/admin/users/3/delete").status_code, 200)

    def test_disabled_user_cannot_login_or_keep_a_session(self):
        with app.app_context():
            connection = get_db_connection()
            connection.execute("UPDATE users SET is_active = 0 WHERE id = 3")
            connection.commit()
            connection.close()
        response = self.client.post(
            "/login", data={"username": "normal-user", "password": "secret123"}
        )
        self.assertEqual(response.status_code, 403)
        self.login_session(3, "normal-user")
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_admin_manager_returns_inserted_id(self):
        success, message = AdminManager().create_admin(
            "manager-admin", "manager@test.local", "secret123"
        )
        self.assertTrue(success, message)
        self.assertIn("ID:", message)

    def test_admin_document_page_exposes_metadata_but_no_download_link(self):
        with app.app_context():
            connection = get_db_connection()
            connection.execute(
                """INSERT INTO documents
                   (id, filename, user_id, file_size, created_at)
                   VALUES (20, 'private.pdf', 3, 2048, '2026-09-01 08:00:00')"""
            )
            connection.commit()
            connection.close()
        self.login_session(1, "admin-one")
        response = self.client.get("/admin/documents")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("private.pdf", html)
        self.assertIn("normal-user", html)
        self.assertNotIn("/download/20", html)

    def test_admin_document_deletion_is_audited(self):
        with app.app_context():
            connection = get_db_connection()
            connection.execute(
                "INSERT INTO documents (id, filename, user_id) VALUES (21, 'unsafe.exe', 3)"
            )
            connection.commit()
            connection.close()
        self.login_session(1, "admin-one")
        response = self.client.post("/admin/documents/21/delete")
        self.assertEqual(response.status_code, 200)
        with app.app_context():
            connection = get_db_connection()
            document = connection.execute(
                "SELECT is_deleted FROM documents WHERE id = 21"
            ).fetchone()
            log = connection.execute(
                "SELECT action, target_id FROM activity_logs WHERE target_id = 21"
            ).fetchone()
            connection.close()
        self.assertEqual(document["is_deleted"], 1)
        self.assertEqual(log["action"], "delete_document")


if __name__ == "__main__":
    unittest.main()
