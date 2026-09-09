"""Shared, read-only database connection helpers for security audits."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from sqlalchemy import create_engine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "database.db"


def create_audit_engine(database_url=None, db_path=None):
    """Create an engine used only by SELECT-based audit code.

    SQLite is opened by a read-only connection creator. MySQL uses the normal
    SQLAlchemy URL, while callers in this package execute SELECT statements
    only. DATABASE_URL takes precedence over DATABASE_PATH.
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
