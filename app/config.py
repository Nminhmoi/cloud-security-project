import os
from datetime import timedelta

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


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "cloud-security-secret-key")
    PERMANENT_SESSION_LIFETIME = timedelta(days=int(os.environ.get("REMEMBER_SESSION_DAYS", "30")))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").strip().lower() == "true"
    DATABASE = _database_path()
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

