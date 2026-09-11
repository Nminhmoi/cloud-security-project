"""Database initialization and transitional SQLite compatibility helpers."""

import sqlite3

from extensions import db
from models import Permission, Role


DEFAULT_ROLES = (
    (1, "admin", "Quản trị viên hệ thống"),
    (2, "user", "Người dùng thông thường"),
)

DEFAULT_PERMISSIONS = (
    (1, "view_documents", "Xem tài liệu"),
    (2, "create_document", "Tạo tài liệu"),
    (3, "edit_document", "Chỉnh sửa tài liệu"),
    (4, "delete_document", "Xóa tài liệu"),
    (5, "share_document", "Chia sẻ tài liệu"),
    (6, "manage_users", "Quản lý người dùng"),
    (7, "manage_roles", "Quản lý vai trò"),
    (8, "view_reports", "Xem báo cáo"),
    (9, "manage_system", "Quản lý hệ thống"),
)


def get_db_connection():
    """Return a SQLAlchemy-managed raw SQLite connection.

    This compatibility API remains temporarily for tests and legacy commands.
    Application code uses ORM sessions and is therefore database independent.
    """
    connection = db.engine.raw_connection()
    if db.engine.dialect.name != "sqlite":
        connection.close()
        raise RuntimeError(
            "Raw database connections are only supported by the local SQLite "
            "compatibility layer; use SQLAlchemy models for other databases."
        )

    connection.driver_connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(app):
    """Create a local schema and seed its RBAC reference data.

    Production disables AUTO_CREATE_SCHEMA and runs ``flask db upgrade``.
    The SQLite compatibility migration keeps existing database.db files usable.
    """
    with app.app_context():
        db.create_all()
        if db.engine.dialect.name == "sqlite":
            _migrate_legacy_sqlite_schema()
        seed_reference_data()


def _migrate_legacy_sqlite_schema():
    connection = get_db_connection()
    try:
        _add_column(connection, "users", "email", "TEXT")
        _add_column(connection, "users", "role_id", "INTEGER DEFAULT 2")
        _add_column(connection, "users", "is_active", "INTEGER DEFAULT 1")
        _add_column(
            connection,
            "users",
            "failed_login_attempts",
            "INTEGER NOT NULL DEFAULT 0",
        )
        _add_column(connection, "users", "locked_until", "TEXT")
        _add_column(
            connection,
            "users",
            "session_version",
            "INTEGER NOT NULL DEFAULT 0",
        )
        connection.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique
               ON users(email) WHERE email IS NOT NULL"""
        )
        _add_column(
            connection, "documents", "is_favorite", "INTEGER NOT NULL DEFAULT 0"
        )
        _add_column(
            connection, "documents", "is_deleted", "INTEGER NOT NULL DEFAULT 0"
        )
        _add_column(connection, "documents", "file_size", "INTEGER NOT NULL DEFAULT 0")
        _add_column(connection, "documents", "storage_key", "TEXT")
        _add_column(connection, "documents", "content_type", "TEXT")
        _add_column(connection, "documents", "sha256", "TEXT")
        _add_column(
            connection,
            "documents",
            "scan_status",
            "TEXT NOT NULL DEFAULT 'not_scanned'",
        )
        _add_column(connection, "documents", "deleted_at", "TEXT")
        connection.execute(
            "UPDATE documents SET storage_key = filename WHERE storage_key IS NULL"
        )
        _add_column(connection, "documents", "created_at", "TEXT")
        connection.execute(
            "UPDATE documents SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
        )
        connection.commit()
    finally:
        connection.close()


def _add_column(connection, table, column, definition):
    columns = {
        row["name"] for row in connection.execute(f"PRAGMA table_info({table})")
    }
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def seed_reference_data():
    """Idempotently seed the built-in roles and permissions."""
    roles = {}
    for role_id, name, description in DEFAULT_ROLES:
        role = db.session.get(Role, role_id)
        if role is None:
            role = Role(id=role_id, name=name, description=description)
            db.session.add(role)
        roles[role_id] = role

    permissions = {}
    for permission_id, name, description in DEFAULT_PERMISSIONS:
        permission = db.session.get(Permission, permission_id)
        if permission is None:
            permission = Permission(
                id=permission_id, name=name, description=description
            )
            db.session.add(permission)
        permissions[permission_id] = permission

    db.session.flush()
    roles[1].permissions = list(permissions.values())
    roles[2].permissions = [permissions[index] for index in range(1, 6)]
    db.session.commit()
