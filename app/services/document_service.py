"""Document lifecycle operations that keep database and object storage aligned."""

from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy import func

from extensions import db
from models import Document
from services.storage_service import delete_stored_file, save_upload, validate_upload


class StorageQuotaExceeded(ValueError):
    """Raised when an upload would exceed the owner's configured quota."""


class DocumentScanPending(RuntimeError):
    """Raised while an asynchronous malware scan has not completed."""


class UnsafeDocument(RuntimeError):
    """Raised when a scan failed or marked a document as infected."""


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def storage_used_by_user(user_id):
    """Count active and trashed files because both still consume storage."""
    return db.session.scalar(
        db.select(func.coalesce(func.sum(Document.file_size), 0)).where(
            Document.user_id == user_id
        )
    )


def ensure_document_downloadable(document):
    if document.scan_status == "pending":
        raise DocumentScanPending("Tài liệu đang chờ kiểm tra an toàn")
    if document.scan_status in {"infected", "failed"}:
        raise UnsafeDocument("Tài liệu không vượt qua kiểm tra an toàn")


def create_document(uploaded_file, user_id):
    metadata = validate_upload(uploaded_file)
    quota = current_app.config["USER_STORAGE_QUOTA_BYTES"]
    used = storage_used_by_user(user_id)
    if quota > 0 and used + metadata.size > quota:
        raise StorageQuotaExceeded("Đã vượt quota lưu trữ của tài khoản")

    storage_key = save_upload(uploaded_file, user_id, metadata)
    try:
        document = Document(
            filename=metadata.filename,
            storage_key=storage_key,
            user_id=user_id,
            file_size=metadata.size,
            content_type=metadata.content_type,
            sha256=metadata.sha256,
            scan_status="not_scanned",
        )
        db.session.add(document)
        db.session.commit()
        return document
    except Exception:
        db.session.rollback()
        try:
            delete_stored_file(storage_key)
        except Exception:
            current_app.logger.exception(
                "Failed to remove orphaned upload %s after database failure",
                storage_key,
            )
        raise


def mark_document_deleted(document):
    document.is_deleted = True
    document.deleted_at = _utcnow()
    db.session.commit()


def restore_document(document):
    document.is_deleted = False
    document.deleted_at = None
    db.session.commit()


def purge_expired_documents(retention_days=None):
    """Permanently remove expired trash and return the number purged."""
    if retention_days is None:
        retention_days = current_app.config["DELETED_DOCUMENT_RETENTION_DAYS"]
    if retention_days < 0:
        raise ValueError("retention_days không được âm")

    cutoff = _utcnow() - timedelta(days=retention_days)
    documents = db.session.scalars(
        db.select(Document).where(
            Document.is_deleted.is_(True),
            Document.deleted_at.is_not(None),
            Document.deleted_at <= cutoff,
        )
    ).all()

    purged = 0
    for document in documents:
        document_id = document.id
        storage_key = document.storage_reference
        try:
            db.session.delete(document)
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                "Skipping document %s because database purge failed", document_id
            )
            continue
        try:
            delete_stored_file(storage_key)
        except Exception:
            current_app.logger.exception(
                "Database row %s was purged but object cleanup failed", document_id
            )
        purged += 1
    return purged


def delete_storage_keys(storage_keys):
    """Best-effort cleanup for keys whose database rows no longer exist."""
    for storage_key in storage_keys:
        try:
            delete_stored_file(storage_key)
        except Exception:
            current_app.logger.exception(
                "Failed to delete storage object %s", storage_key
            )
