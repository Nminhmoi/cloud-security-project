import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "cloud-security-secret-key")
    DATABASE = os.environ.get("DATABASE_PATH", os.path.join(PROJECT_ROOT, "database.db"))
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

