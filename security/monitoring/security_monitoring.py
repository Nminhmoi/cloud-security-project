#!/usr/bin/env python3
"""Point-in-time CloudBox application security audit.

The monitor reports INCOMPLETE when brute-force telemetry is unavailable. It
must never translate missing evidence into a claim that the system is secure.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from security.database import create_audit_engine


@dataclass
class SecurityAuditResult:
    status: str
    metrics: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)
    coverage_complete: bool = False


class SecurityMonitor:
    """Run read-only account and login-abuse checks against SQLite or MySQL."""

    def __init__(self, db_path=None, database_url=None):
        self.db_path = db_path
        self.database_url = database_url

    def audit(self):
        engine = create_audit_engine(
            database_url=self.database_url,
            db_path=self.db_path,
        )
        try:
            schema = inspect(engine)
            tables = set(schema.get_table_names())
            if "users" not in tables:
                raise ValueError("Required table 'users' does not exist")

            user_columns = {
                column["name"] for column in schema.get_columns("users")
            }
            metrics = {}
            warnings = []
            alerts = []

            with engine.connect() as connection:
                metrics["total_users"] = connection.execute(
                    text("SELECT COUNT(*) FROM users")
                ).scalar_one()

                if "roles" in tables and "role_id" in user_columns:
                    metrics["total_admins"] = connection.execute(
                        text(
                            "SELECT COUNT(*) FROM users u "
                            "JOIN roles r ON u.role_id = r.id "
                            "WHERE r.name = 'admin'"
                        )
                    ).scalar_one()
                else:
                    metrics["total_admins"] = None
                    warnings.append("Admin count unavailable: roles relation is missing.")

                brute_force_covered = self._audit_login_failures(
                    connection,
                    tables,
                    user_columns,
                    warnings,
                    alerts,
                    metrics,
                )

                if "activity_logs" in tables:
                    metrics["recent_activities"] = connection.execute(
                        text("SELECT COUNT(*) FROM (SELECT id FROM activity_logs ORDER BY id DESC LIMIT 10) recent")
                    ).scalar_one()
                else:
                    metrics["recent_activities"] = 0
                    warnings.append("Administrative activity log table is missing.")

            if alerts:
                status = "ALERT"
            elif not brute_force_covered:
                status = "INCOMPLETE"
            elif warnings:
                status = "REVIEW"
            else:
                status = "NO_FINDINGS"

            return SecurityAuditResult(
                status=status,
                metrics=metrics,
                warnings=warnings,
                alerts=alerts,
                coverage_complete=brute_force_covered,
            )
        finally:
            engine.dispose()

    @staticmethod
    def _audit_login_failures(
        connection,
        tables,
        user_columns,
        warnings,
        alerts,
        metrics,
    ):
        required_columns = {"failed_login_attempts", "locked_until"}
        if required_columns.issubset(user_columns):
            failed_users = connection.execute(
                text(
                    "SELECT username, failed_login_attempts, locked_until "
                    "FROM users WHERE failed_login_attempts > 0"
                )
            ).mappings()
            failure_count = 0
            for user in failed_users:
                attempts = int(user["failed_login_attempts"] or 0)
                failure_count += attempts
                message = (
                    f"Account '{user['username']}' has {attempts} failed login "
                    "attempt(s)."
                )
                if attempts >= 5:
                    alerts.append(message)
                else:
                    warnings.append(message)
            metrics["failed_login_attempts"] = failure_count
            metrics["login_telemetry_source"] = "users"
            return True

        if "activity_logs" in tables:
            activity_columns = {
                column["name"]
                for column in inspect(connection).get_columns("activity_logs")
            }
            if "action" in activity_columns:
                failed_events = connection.execute(
                    text(
                        "SELECT COUNT(*) FROM activity_logs "
                        "WHERE action IN ('login_failed', 'failed_login')"
                    )
                ).scalar_one()
                metrics["failed_login_events"] = failed_events
                metrics["login_telemetry_source"] = "activity_logs"
                if failed_events:
                    warnings.append(
                        f"Found {failed_events} failed-login event(s); event-based "
                        "thresholding is not configured yet."
                    )
                else:
                    warnings.append(
                        "No failed-login events exist. The application may not be "
                        "recording authentication failures."
                    )
                return False

        metrics["login_telemetry_source"] = "none"
        warnings.append(
            "Brute-force monitoring unavailable: neither failed-login account "
            "fields nor authentication-failure events exist."
        )
        return False

    def run_security_audit(self):
        """Print the report and return whether the audit executed successfully."""

        try:
            result = self.audit()
        except (FileNotFoundError, ValueError, SQLAlchemyError) as error:
            print(f"[ERROR] Security audit failed: {error}")
            return False

        print("\n" + "=" * 72)
        print("CLOUDBOX POINT-IN-TIME SECURITY AUDIT")
        print("=" * 72)
        print(f"Status: {result.status}")
        print(f"Total users: {result.metrics.get('total_users')}")
        print(f"Total admins: {result.metrics.get('total_admins')}")
        print(f"Recent administrative activities: {result.metrics.get('recent_activities')}")
        print(
            "Login telemetry source: "
            f"{result.metrics.get('login_telemetry_source')}"
        )
        for warning in result.warnings:
            print(f"[WARN] {warning}")
        for alert in result.alerts:
            print(f"[ALERT] {alert}")
        if result.status == "NO_FINDINGS":
            print("[PASS] No findings were detected by the implemented checks.")
        elif result.status == "INCOMPLETE":
            print("[INCOMPLETE] Missing telemetry prevents a security conclusion.")
        print("This is a point-in-time audit, not real-time monitoring.")
        return True


def main():
    parser = argparse.ArgumentParser(description="Run the CloudBox security audit")
    parser.add_argument("--database-url", help="SQLAlchemy SQLite/MySQL database URL")
    parser.add_argument("--db", help="SQLite path when DATABASE_URL is not used")
    args = parser.parse_args()
    monitor = SecurityMonitor(db_path=args.db, database_url=args.database_url)
    return 0 if monitor.run_security_audit() else 1


if __name__ == "__main__":
    sys.exit(main())
