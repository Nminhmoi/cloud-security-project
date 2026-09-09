"""Tests for the point-in-time security audit and alarm example."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from security.monitoring.security_monitoring import SecurityMonitor


class SecurityMonitoringTests(unittest.TestCase):
    def setUp(self):
        self.policies_directory = Path(__file__).resolve().parents[1] / "policies"
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        self.database_path = Path(handle.name)
        self.addCleanup(self.database_path.unlink, missing_ok=True)

    def _create_database(self, include_login_fields=False, failed_attempts=0):
        login_fields = (
            ", failed_login_attempts INTEGER NOT NULL DEFAULT 0, locked_until TEXT"
            if include_login_fields
            else ""
        )
        connection = sqlite3.connect(self.database_path)
        connection.executescript(
            f"""
            CREATE TABLE roles (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                role_id INTEGER NOT NULL
                {login_fields}
            );
            CREATE TABLE activity_logs (
                id INTEGER PRIMARY KEY,
                action TEXT NOT NULL,
                created_at TEXT
            );
            INSERT INTO roles (id, name) VALUES (1, 'admin'), (2, 'user');
            INSERT INTO users (id, username, password, role_id{', failed_login_attempts' if include_login_fields else ''})
            VALUES (1, 'admin#1', 'scrypt:test', 1{f', {failed_attempts}' if include_login_fields else ''});
            """
        )
        connection.commit()
        connection.close()

    def test_cloudwatch_alarm_has_expected_schema(self):
        alarm_path = self.policies_directory / "cloudwatch_alarms.json"
        with alarm_path.open("r", encoding="utf-8") as alarm_file:
            alarm = json.load(alarm_file)

        self.assertEqual(
            alarm["Namespace"], "CloudSecurityApp/Authentication"
        )
        self.assertEqual(alarm["MetricName"], "FailedLoginAttempts")
        self.assertEqual(alarm["Statistic"], "Sum")
        self.assertGreaterEqual(alarm["Threshold"], 1)
        self.assertEqual(
            alarm["ComparisonOperator"], "GreaterThanOrEqualToThreshold"
        )

    def test_missing_login_telemetry_reports_incomplete(self):
        self._create_database()
        result = SecurityMonitor(db_path=self.database_path).audit()

        self.assertEqual(result.status, "INCOMPLETE")
        self.assertFalse(result.coverage_complete)
        self.assertTrue(any("may not be recording" in item for item in result.warnings))

    def test_failed_login_threshold_reports_alert(self):
        self._create_database(include_login_fields=True, failed_attempts=5)
        result = SecurityMonitor(db_path=self.database_path).audit()

        self.assertEqual(result.status, "ALERT")
        self.assertTrue(result.coverage_complete)
        self.assertEqual(result.metrics["failed_login_attempts"], 5)
        self.assertEqual(len(result.alerts), 1)

    def test_missing_database_fails_without_creating_it(self):
        missing_path = self.database_path.with_name("missing-security-audit.db")
        missing_path.unlink(missing_ok=True)

        self.assertFalse(SecurityMonitor(db_path=missing_path).run_security_audit())
        self.assertFalse(missing_path.exists())


if __name__ == "__main__":
    unittest.main()
