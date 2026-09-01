import sqlite3
from flask import current_app


def get_db_connection():
    connection = sqlite3.connect(current_app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(app):
    with app.app_context():
        connection = get_db_connection()
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT
            );
            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT
            );
            CREATE TABLE IF NOT EXISTS role_permissions (
                role_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                PRIMARY KEY (role_id, permission_id),
                FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
                FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                password TEXT NOT NULL,
                role_id INTEGER DEFAULT 2,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (role_id) REFERENCES roles(id)
            );
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS document_shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                shared_with_user_id INTEGER NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                FOREIGN KEY (shared_with_user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(document_id, shared_with_user_id)
            );
            CREATE TABLE IF NOT EXISTS password_reset_otps (
                user_id INTEGER PRIMARY KEY,
                otp_hash TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_user_id INTEGER,
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id INTEGER,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE SET NULL
            );
        """)

        # Chèn roles mặc định
        _insert_default_roles(connection)
        # Chèn permissions mặc định
        _insert_default_permissions(connection)
        # Gán permissions cho roles
        _assign_role_permissions(connection)

        _add_column(connection, "users", "email", "TEXT")
        # Migrate databases created before RBAC was introduced. Existing
        # accounts remain active regular users until an admin is assigned.
        _add_column(connection, "users", "role_id", "INTEGER DEFAULT 2")
        _add_column(connection, "users", "is_active", "INTEGER DEFAULT 1")
        connection.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique
            ON users(email) WHERE email IS NOT NULL
        """)
        _add_column(connection, "documents", "is_favorite", "INTEGER NOT NULL DEFAULT 0")
        _add_column(connection, "documents", "is_deleted", "INTEGER NOT NULL DEFAULT 0")
        _add_column(connection, "documents", "file_size", "INTEGER NOT NULL DEFAULT 0")
        _add_column(connection, "documents", "created_at", "TEXT")
        connection.execute(
            "UPDATE documents SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
        )
        connection.commit()
        connection.close()


def _add_column(connection, table, column, definition):
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _insert_default_roles(connection):
    """Chèn các role mặc định"""
    try:
        connection.execute("INSERT OR IGNORE INTO roles (id, name, description) VALUES (1, 'admin', 'Quản trị viên hệ thống')")
        connection.execute("INSERT OR IGNORE INTO roles (id, name, description) VALUES (2, 'user', 'Người dùng thông thường')")
        connection.commit()
    except sqlite3.IntegrityError:
        pass


def _insert_default_permissions(connection):
    """Chèn các permission mặc định"""
    permissions = [
        (1, 'view_documents', 'Xem tài liệu'),
        (2, 'create_document', 'Tạo tài liệu'),
        (3, 'edit_document', 'Chỉnh sửa tài liệu'),
        (4, 'delete_document', 'Xóa tài liệu'),
        (5, 'share_document', 'Chia sẻ tài liệu'),
        (6, 'manage_users', 'Quản lý người dùng'),
        (7, 'manage_roles', 'Quản lý vai trò'),
        (8, 'view_reports', 'Xem báo cáo'),
        (9, 'manage_system', 'Quản lý hệ thống'),
    ]

    try:
        for perm_id, name, description in permissions:
            connection.execute(
                "INSERT OR IGNORE INTO permissions (id, name, description) VALUES (?, ?, ?)",
                (perm_id, name, description)
            )
        connection.commit()
    except sqlite3.IntegrityError:
        pass


def _assign_role_permissions(connection):
    """Gán permissions cho các role"""
    try:
        # Admin có tất cả quyền
        admin_permissions = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        for perm_id in admin_permissions:
            connection.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (1, ?)",
                (perm_id,)
            )

        # User thông thường chỉ có một số quyền
        user_permissions = [1, 2, 3, 4, 5]  # view, create, edit, delete, share
        for perm_id in user_permissions:
            connection.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (2, ?)",
                (perm_id,)
            )

        connection.commit()
    except sqlite3.IntegrityError:
        pass
