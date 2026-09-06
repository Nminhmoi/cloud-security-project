import os
from datetime import timedelta
from pathlib import Path

from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DEFAULT_DATABASE = os.path.join(PROJECT_ROOT, "database.db")


def _database_path():
    configured_path = os.environ.get("DATABASE_PATH")
    if not configured_path:
        return DEFAULT_DATABASE

    # The workspace preview runner injects a disposable empty database. Using it
    # would make accounts registered in preview disappear when the local server
    # is opened, so local preview and local Flask share the project database.
    if os.path.basename(configured_path).casefold() == ".overdrive-preview.db":
        return DEFAULT_DATABASE
    return configured_path


def _database_uri():
    """Return the SQLAlchemy URI while retaining SQLite as the local default."""
    configured_uri = os.environ.get("DATABASE_URL", "").strip()
    if configured_uri:
        # Accept the common short scheme but select the maintained PyMySQL
        # driver explicitly for production deployments.
        if configured_uri.startswith("mysql://"):
            return configured_uri.replace("mysql://", "mysql+pymysql://", 1)
        return configured_uri

    mysql_host = os.environ.get("DB_HOST", "").strip()
    if mysql_host:
        settings = {
            "DB_USER": os.environ.get("DB_USER", "").strip(),
            "DB_PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "DB_NAME": os.environ.get("DB_NAME", "").strip(),
        }
        missing = [name for name, value in settings.items() if not value]
        if missing:
            raise RuntimeError(
                "Missing MySQL configuration: " + ", ".join(sorted(missing))
            )
        try:
            port = int(os.environ.get("DB_PORT", "3306"))
        except ValueError as error:
            raise RuntimeError("DB_PORT must be an integer") from error

        # URL.create safely escapes passwords containing characters such as
        # @, :, or / before SQLAlchemy passes the URL to PyMySQL.
        return URL.create(
            "mysql+pymysql",
            username=settings["DB_USER"],
            password=settings["DB_PASSWORD"],
            host=mysql_host,
            port=port,
            database=settings["DB_NAME"],
            query={"charset": "utf8mb4"},
        ).render_as_string(hide_password=False)

    database_path = Path(_database_path()).resolve().as_posix()
    return f"sqlite:///{database_path}"


def _engine_options(database_uri):
    if database_uri.startswith("sqlite:"):
        # SQLite is a local/test backend. Avoid retaining Windows file handles
        # and let each short request own exactly one physical connection.
        return {"poolclass": NullPool}
    options = {"pool_pre_ping": True, "pool_recycle": 280}
    ssl_ca = os.environ.get("DB_SSL_CA", "").strip()
    if ssl_ca:
        options["connect_args"] = {"ssl": {"ca": ssl_ca}}
    return options


DATABASE_URI = _database_uri()


def _secret_key():
    configured_secret = os.environ.get("SECRET_KEY", "").strip()
    if configured_secret:
        return configured_secret
    if not DATABASE_URI.startswith("sqlite:"):
        raise RuntimeError("SECRET_KEY is required when using a shared database")
    return "cloud-security-local-development-only"


class Config:
    SECRET_KEY = _secret_key()
    PERMANENT_SESSION_LIFETIME = timedelta(days=int(os.environ.get("REMEMBER_SESSION_DAYS", "30")))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").strip().lower() == "true"
    DATABASE = _database_path()
    SQLALCHEMY_DATABASE_URI = DATABASE_URI
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options(DATABASE_URI)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    AUTO_CREATE_SCHEMA = os.environ.get(
        "AUTO_CREATE_SCHEMA", "true" if DATABASE_URI.startswith("sqlite:") else "false"
    ).strip().lower() == "true"
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(BASE_DIR, "uploads"))
    OTP_DELIVERY_MODE = os.environ.get("OTP_DELIVERY_MODE", "local").strip().lower()
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    SMTP_FROM = os.environ.get("SMTP_FROM")
    AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-1")
    AWS_S3_BUCKET = os.environ.get("AWS_S3_BUCKET")
    AWS_SES_SENDER = os.environ.get("AWS_SES_SENDER")

