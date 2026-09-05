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
            connection.execute("DELETE FROM activity_logs")
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
        self.assertTrue(user_response.headers["Location"].endswith("/documents"))

    def test_admin_cannot_land_in_the_user_document_workspace(self):
        self.login_session(1, "admin-one")

        response = self.client.get("/documents")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/admin/dashboard"))

    def test_remember_me_controls_permanent_session(self):
        response = self.client.post(
            "/login",
            data={
                "username": "normal-user",
                "password": "secret123",
                "remember_me": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as login_session:
            self.assertTrue(login_session.permanent)

        self.client.get("/logout")
        response = self.client.post(
            "/login", data={"username": "normal-user", "password": "secret123"}
        )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as login_session:
            self.assertFalse(login_session.permanent)

    def test_login_accepts_trimmed_case_insensitive_username_or_email(self):
        by_username = self.client.post(
            "/login", data={"username": "  ADMIN-ONE  ", "password": "secret123"}
        )
        self.assertEqual(by_username.status_code, 302)
        self.assertTrue(by_username.headers["Location"].endswith("/admin/dashboard"))

        self.client.get("/logout")
        by_email = self.client.post(
            "/login", data={"username": "USER@TEST.LOCAL", "password": "secret123"}
        )
        self.assertEqual(by_email.status_code, 302)
        self.assertTrue(by_email.headers["Location"].endswith("/documents"))

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

    def test_admin_can_change_user_role(self):
        self.login_session(1, "admin-one")

        response = self.client.post("/admin/users/3/role", json={"role_id": 1})
        user_response = self.client.get("/admin/users/3")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(user_response.status_code, 200)
        self.assertEqual(user_response.get_json()["role_id"], 1)
        self.assertEqual(user_response.get_json()["role_name"], "admin")

    def test_admin_can_revoke_and_assign_role_permission(self):
        self.login_session(1, "admin-one")

        revoked = self.client.post(
            "/admin/roles/2/revoke-permission", json={"permission_id": 5}
        )
        self.assertEqual(revoked.status_code, 200)
        permissions = self.client.get("/admin/roles/2/permissions").get_json()
        self.assertNotIn(5, [permission["id"] for permission in permissions])

        assigned = self.client.post(
            "/admin/roles/2/assign-permission", json={"permission_id": 5}
        )
        self.assertEqual(assigned.status_code, 200)
        permissions = self.client.get("/admin/roles/2/permissions").get_json()
        self.assertIn(5, [permission["id"] for permission in permissions])

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

    def test_toggle_user_active_is_audited(self):
        self.login_session(1, "admin-one")

        disable_response = self.client.post("/admin/users/3/toggle-active")
        enable_response = self.client.post("/admin/users/3/toggle-active")

        self.assertEqual(disable_response.status_code, 200)
        self.assertEqual(disable_response.get_json()["is_active"], 0)
        self.assertEqual(enable_response.status_code, 200)
        self.assertEqual(enable_response.get_json()["is_active"], 1)
        with app.app_context():
            connection = get_db_connection()
            user = connection.execute(
                "SELECT is_active FROM users WHERE id = 3"
            ).fetchone()
            logs = connection.execute(
                """SELECT actor_user_id, action, target_type, target_id, details
                   FROM activity_logs ORDER BY id"""
            ).fetchall()
            connection.close()
        self.assertEqual(user["is_active"], 1)
        self.assertEqual([log["action"] for log in logs], ["disable_user", "enable_user"])
        for log in logs:
            self.assertEqual(log["actor_user_id"], 1)
            self.assertEqual(log["target_type"], "user")
            self.assertEqual(log["target_id"], 3)
            self.assertIn("normal-user", log["details"])

    def test_delete_user_is_audited_and_keeps_target_identity(self):
        self.login_session(1, "admin-one")

        response = self.client.post("/admin/users/3/delete")

        self.assertEqual(response.status_code, 200)
        with app.app_context():
            connection = get_db_connection()
            user = connection.execute("SELECT 1 FROM users WHERE id = 3").fetchone()
            log = connection.execute(
                """SELECT actor_user_id, action, target_type, target_id, details
                   FROM activity_logs"""
            ).fetchone()
            connection.close()
        self.assertIsNone(user)
        self.assertEqual(log["actor_user_id"], 1)
        self.assertEqual(log["action"], "delete_user")
        self.assertEqual(log["target_type"], "user")
        self.assertEqual(log["target_id"], 3)
        self.assertIn("normal-user", log["details"])

    def test_user_management_api_requires_admin(self):
        self.login_session(3, "normal-user")

        toggle_response = self.client.post("/admin/users/2/toggle-active")
        delete_response = self.client.post("/admin/users/2/delete")

        self.assertEqual(toggle_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        with app.app_context():
            connection = get_db_connection()
            target = connection.execute(
                "SELECT is_active FROM users WHERE id = 2"
            ).fetchone()
            log_count = connection.execute(
                "SELECT COUNT(*) AS count FROM activity_logs"
            ).fetchone()["count"]
            connection.close()
        self.assertEqual(target["is_active"], 1)
        self.assertEqual(log_count, 0)

    def test_rejected_self_management_does_not_create_audit_log(self):
        self.login_session(1, "admin-one")

        toggle_response = self.client.post("/admin/users/1/toggle-active")
        delete_response = self.client.post("/admin/users/1/delete")

        self.assertEqual(toggle_response.status_code, 400)
        self.assertEqual(delete_response.status_code, 400)
        with app.app_context():
            connection = get_db_connection()
            admin = connection.execute(
                "SELECT is_active FROM users WHERE id = 1"
            ).fetchone()
            log_count = connection.execute(
                "SELECT COUNT(*) AS count FROM activity_logs"
            ).fetchone()["count"]
            connection.close()
        self.assertEqual(admin["is_active"], 1)
        self.assertEqual(log_count, 0)

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
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("CloudBox", response.get_data(as_text=True))

    def test_public_home_and_authenticated_home_redirects(self):
        public_response = self.client.get("/")
        self.assertEqual(public_response.status_code, 200)
        self.assertIn("Tài liệu của nhóm", public_response.get_data(as_text=True))
        self.assertIn("Năng lực bảo vệ CloudBox", public_response.get_data(as_text=True))
        self.assertIn("Đã triển khai và kiểm thử", public_response.get_data(as_text=True))
        self.assertNotIn("Đang phát triển / dự kiến", public_response.get_data(as_text=True))
        self.assertIn("Triển khai trên AWS", public_response.get_data(as_text=True))

        self.login_session(3, "normal-user")
        user_response = self.client.get("/")
        self.assertEqual(user_response.status_code, 302)
        self.assertTrue(user_response.headers["Location"].endswith("/documents"))

    def test_browser_login_failure_stays_on_login_page_and_clears_fields(self):
        response = self.client.post(
            "/login",
            data={"username": "normal-user", "password": "wrong-password"},
        )

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 401)
        self.assertIn('id="login-form"', body)
        self.assertIn('id="login-error"', body)
        self.assertIn("Sai tài khoản hoặc mật khẩu!", body)
        self.assertNotIn('value="normal-user"', body)
        self.assertNotIn('value="wrong-password"', body)

    def test_async_login_returns_inline_error_or_role_redirect(self):
        headers = {"Accept": "application/json"}
        failed = self.client.post(
            "/login",
            data={"username": "normal-user", "password": "wrong-password"},
            headers=headers,
        )
        self.assertEqual(failed.status_code, 401)
        self.assertEqual(
            failed.get_json()["error"]["message"],
            "Sai tài khoản hoặc mật khẩu!",
        )

        succeeded = self.client.post(
            "/login",
            data={"username": "normal-user", "password": "secret123"},
            headers=headers,
        )
        self.assertEqual(succeeded.status_code, 200)
        self.assertTrue(
            succeeded.get_json()["data"]["redirect_url"].endswith("/documents")
        )

        self.client.get("/logout")
        self.login_session(1, "admin-one")
        admin_response = self.client.get("/")
        self.assertEqual(admin_response.status_code, 302)
        self.assertTrue(admin_response.headers["Location"].endswith("/admin/dashboard"))

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
