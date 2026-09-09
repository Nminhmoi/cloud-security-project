"""Tests for IAM policy validation and read-only account auditing."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import inspect

from security.database import create_audit_engine
from security.iam.iam_validator import IAMPolicyValidator, scan_directory
from security.iam.user_evaluator import evaluate_user_accounts


class IAMSecurityTests(unittest.TestCase):
    def setUp(self):
        self.policies_directory = Path(__file__).resolve().parents[1] / "policies"

    def _temporary_policy(self, policy):
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".json", encoding="utf-8", delete=False
        )
        with handle:
            json.dump(policy, handle)
        self.addCleanup(Path(handle.name).unlink, missing_ok=True)
        return handle.name

    def test_project_iam_policies_pass(self):
        for name in ("s3_policy.json", "ses_policy.json", "admin_policy.json"):
            with self.subTest(policy=name):
                validator = IAMPolicyValidator(self.policies_directory / name)
                self.assertTrue(validator.validate(), validator.errors)

    def test_scan_policy_directory(self):
        self.assertTrue(scan_directory(self.policies_directory))

    def test_rejects_allow_all(self):
        path = self._temporary_policy(
            {
                "Version": "2012-10-17",
                "Statement": {"Effect": "Allow", "Action": "*", "Resource": "*"},
            }
        )
        validator = IAMPolicyValidator(path)
        self.assertFalse(validator.validate())
        self.assertTrue(any("Action '*'" in error for error in validator.errors))

    def test_rejects_missing_action_and_resource(self):
        path = self._temporary_policy(
            {"Version": "2012-10-17", "Statement": {"Effect": "Allow"}}
        )
        validator = IAMPolicyValidator(path)
        self.assertFalse(validator.validate())
        self.assertTrue(any("Action" in error for error in validator.errors))
        self.assertTrue(any("Resource" in error for error in validator.errors))

    def test_rejects_s3_policy_without_transport_deny(self):
        path = self._temporary_policy(
            {
                "Version": "2012-10-17",
                "Statement": {
                    "Effect": "Allow",
                    "Action": "s3:GetObject",
                    "Resource": "arn:aws:s3:::example-bucket/*",
                },
            }
        )
        validator = IAMPolicyValidator(path)
        self.assertFalse(validator.validate())
        self.assertTrue(
            any("SecureTransport" in error for error in validator.errors)
        )


class UserAccountAuditTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        self.database_path = Path(handle.name)
        self.addCleanup(self.database_path.unlink, missing_ok=True)

        connection = sqlite3.connect(self.database_path)
        connection.executescript(
            """
            CREATE TABLE roles (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            );
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                email TEXT,
                password TEXT NOT NULL,
                role_id INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            );
            INSERT INTO roles (id, name) VALUES (1, 'admin'), (2, 'user');
            INSERT INTO users
                (id, username, email, password, role_id, is_active)
            VALUES
                (1, 'admin#1', 'admin@example.test', 'scrypt:32768:8:1$hash', 1, 1),
                (2, 'user#22', 'user@example.test', 'pbkdf2:sha256$hash', 2, 0);
            """
        )
        connection.commit()
        connection.close()

    def test_account_audit_is_read_only_and_does_not_expose_hashes(self):
        before_engine = create_audit_engine(db_path=self.database_path)
        before_columns = {
            column["name"] for column in inspect(before_engine).get_columns("users")
        }
        before_engine.dispose()

        report = evaluate_user_accounts(db_path=self.database_path)

        after_engine = create_audit_engine(db_path=self.database_path)
        after_columns = {
            column["name"] for column in inspect(after_engine).get_columns("users")
        }
        after_engine.dispose()

        self.assertEqual(report["total_users"], 2)
        self.assertEqual(report["active_users"], 1)
        self.assertEqual(report["unknown_password_schemes"], 0)
        self.assertNotIn("password", report["users"][0])
        self.assertEqual(before_columns, after_columns)
        self.assertNotIn("created_at", after_columns)


if __name__ == "__main__":
    unittest.main()
