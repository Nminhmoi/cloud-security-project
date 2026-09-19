"""Các hàm kết nối cơ sở dữ liệu chỉ đọc dùng chung cho kiểm toán bảo mật."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from sqlalchemy import create_engine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "database.db"


def create_audit_engine(database_url=None, db_path=None):
    """Tạo đối tượng kết nối chỉ dành cho mã kiểm toán sử dụng SELECT.

    SQLite được mở bằng hàm tạo kết nối chỉ đọc. MySQL sử dụng URL
    SQLAlchemy thông thường; các hàm gọi trong gói này chỉ thực thi
    câu lệnh SELECT. DATABASE_URL được ưu tiên hơn DATABASE_PATH.
    """

    configured_url = (database_url or os.environ.get("DATABASE_URL", "")).strip()
    if configured_url:
        if configured_url.startswith("mysql://"):
            configured_url = configured_url.replace("mysql://", "mysql+pymysql://", 1)
        return create_engine(configured_url, pool_pre_ping=True)

    database_file = Path(
        db_path or os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH)
    ).resolve()
    if not database_file.is_file():
        raise FileNotFoundError(f"Database does not exist: {database_file}")

    def open_read_only_sqlite():
        return sqlite3.connect(
            f"file:{database_file.as_posix()}?mode=ro",
            uri=True,
        )

    return create_engine("sqlite+pysqlite://", creator=open_read_only_sqlite)
