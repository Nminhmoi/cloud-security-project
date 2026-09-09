#!/usr/bin/env python3
"""Read-only audit of CloudBox user accounts."""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from security.database import create_audit_engine


def _mask_email(value):
    if not value or "@" not in value:
        return "N/A"
    local_part, domain = value.rsplit("@", 1)
    visible = local_part[:1]
    return f"{visible}{'*' * max(3, len(local_part) - 1)}@{domain}"


def evaluate_user_accounts(database_url=None, db_path=None):
    """Return account metadata without changing schema or exposing hashes."""

    engine = create_audit_engine(database_url=database_url, db_path=db_path)
    try:
        schema = inspect(engine)
        tables = set(schema.get_table_names())
        if "users" not in tables:
            raise ValueError("Required table 'users' does not exist")

        user_columns = {column["name"] for column in schema.get_columns("users")}
        required_columns = {"id", "username", "password"}
        missing_columns = sorted(required_columns - user_columns)
        if missing_columns:
            raise ValueError(
                "users table is missing required columns: "
                + ", ".join(missing_columns)
            )

        email_expression = "u.email" if "email" in user_columns else "NULL"
        active_expression = (
            "u.is_active" if "is_active" in user_columns else "NULL"
        )
        created_expression = (
            "u.created_at" if "created_at" in user_columns else "NULL"
        )
        has_roles = "roles" in tables and "role_id" in user_columns
        role_expression = "COALESCE(r.name, 'unassigned')" if has_roles else "'unknown'"
        role_join = "LEFT JOIN roles r ON u.role_id = r.id" if has_roles else ""

        statement = text(
            f"""
            SELECT
                u.id,
                u.username,
                {email_expression} AS email,
                {active_expression} AS is_active,
                {created_expression} AS created_at,
                {role_expression} AS role_name,
                CASE
                    WHEN u.password LIKE 'scrypt:%' THEN 'scrypt'
                    WHEN u.password LIKE 'pbkdf2:%' THEN 'pbkdf2'
                    WHEN u.password IS NULL OR u.password = '' THEN 'missing'
                    ELSE 'unknown'
                END AS password_scheme
            FROM users u
            {role_join}
            ORDER BY u.id
            """
        )
        with engine.connect() as connection:
            rows = [dict(row) for row in connection.execute(statement).mappings()]

        return {
            "users": rows,
            "total_users": len(rows),
            "active_users": sum(bool(row["is_active"]) for row in rows),
            "unknown_password_schemes": sum(
                row["password_scheme"] not in {"scrypt", "pbkdf2"} for row in rows
            ),
            "created_at_available": "created_at" in user_columns,
        }
    finally:
        engine.dispose()


def list_user_accounts(database_url=None, db_path=None):
    """Print a privacy-conscious account report and return execution success."""

    try:
        report = evaluate_user_accounts(database_url=database_url, db_path=db_path)
    except (FileNotFoundError, ValueError, SQLAlchemyError) as error:
        print(f"[ERROR] Account audit failed: {error}")
        return False

    print("\n" + "=" * 88)
    print("CLOUDBOX USER ACCOUNT AUDIT (READ ONLY)")
    print("=" * 88)
    print(f"Total users: {report['total_users']}")
    print(f"Active users: {report['active_users']}")
    if not report["created_at_available"]:
        print("[INFO] users.created_at is not present; creation time is unavailable.")

    print("ID | Username | Email (masked) | Role | Active | Password scheme | Created")
    for user in report["users"]:
        print(
            f"{user['id']} | {user['username']} | {_mask_email(user['email'])} | "
            f"{user['role_name']} | {user['is_active']} | "
            f"{user['password_scheme']} | {user['created_at'] or 'N/A'}"
        )

    if report["unknown_password_schemes"]:
        print(
            "[WARN] "
            f"{report['unknown_password_schemes']} account(s) use a missing or "
            "unrecognized password scheme."
        )
    else:
        print("[PASS] All accounts use a recognized password hashing scheme.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Run a read-only user account audit")
    parser.add_argument("--database-url", help="SQLAlchemy SQLite/MySQL database URL")
    parser.add_argument("--db", help="SQLite path when DATABASE_URL is not used")
    args = parser.parse_args()
    return 0 if list_user_accounts(args.database_url, args.db) else 1


if __name__ == "__main__":
    sys.exit(main())
