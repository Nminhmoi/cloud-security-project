"""Shared Flask extensions.

Extensions live in their own module so they can be initialized by the app
factory without creating circular imports.
"""

import sqlite3

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine


db = SQLAlchemy()
migrate = Migrate(compare_type=True)
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    """Make local SQLite enforce the same foreign keys as MySQL."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
