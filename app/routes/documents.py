"""Browser routes for document management."""

from flask import Blueprint, redirect, render_template, request, session, url_for
from sqlalchemy import or_

from extensions import db, limiter
from models import Document, DocumentShare, User
from permissions import require_permission
from services.document_service import (
    DocumentScanPending,
    StorageQuotaExceeded,
    UnsafeDocument,
    create_document,
    ensure_document_downloadable,
    mark_document_deleted,
    restore_document as restore_document_record,
)
from services.storage_service import send_stored_file

documents_bp = Blueprint("documents", __name__)


def _is_logged_in():
    return "user_id" in session


@documents_bp.route("/")
def home():
    if not _is_logged_in():
        return render_template("home.html")

    user = db.session.get(User, session["user_id"])
    if user and user.role_name == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("documents.index"))


@documents_bp.route("/documents")
@require_permission("view_documents")
def index():
    if not _is_logged_in():
        return redirect(url_for("auth.login"))

    user = db.session.get(User, session["user_id"])
    if user and user.role_name == "admin":
        return redirect(url_for("admin.dashboard"))

    documents = db.session.scalars(
        db.select(Document).where(
            Document.user_id == session["user_id"], Document.is_deleted.is_(False)
        )
    ).all()
    shared_documents = db.session.scalars(
        db.select(Document)
        .join(DocumentShare)
        .where(
            DocumentShare.shared_with_user_id == session["user_id"],
            Document.is_deleted.is_(False),
        )
    ).all()
    deleted_documents = db.session.scalars(
        db.select(Document).where(
            Document.user_id == session["user_id"], Document.is_deleted.is_(True)
        )
    ).all()

    document_rows = [document.to_dict() for document in documents]
    shared_rows = []
    for document in shared_documents:
        row = document.to_dict()
        row["owner"] = document.owner.username
        shared_rows.append(row)

    return render_template(
        "index.html",
        documents=document_rows,
        shared_documents=shared_rows,
        deleted_documents=[document.to_dict() for document in deleted_documents],
        active_view=request.args.get("view", "mine"),
    )


@documents_bp.route("/upload", methods=["POST"])
@limiter.limit("10 per minute")
@require_permission("create_document")
def upload():
    if not _is_logged_in():
        return redirect(url_for("auth.login"))

    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return "Chưa chọn file!", 400

    try:
        document = create_document(uploaded_file, session["user_id"])
    except StorageQuotaExceeded as error:
        return str(error), 413
    except ValueError as error:
        return str(error), 400
    return redirect(url_for("documents.index", uploaded=document.filename))


def _accessible_document(document_id):
    return db.session.scalar(
        db.select(Document).where(
            Document.id == document_id,
            Document.is_deleted.is_(False),
            or_(
                Document.user_id == session["user_id"],
                Document.shares.any(
                    DocumentShare.shared_with_user_id == session["user_id"]
                ),
            ),
        )
    )


@documents_bp.route("/download/<int:document_id>")
@require_permission("view_documents")
def download(document_id):
    if not _is_logged_in():
        return redirect(url_for("auth.login"))
    document = _accessible_document(document_id)
    if not document:
        return "Bạn không có quyền truy cập tài liệu này!", 403
    try:
        ensure_document_downloadable(document)
    except DocumentScanPending as error:
        return str(error), 423
    except UnsafeDocument as error:
        return str(error), 403
    return send_stored_file(document.storage_reference, document.filename)


@documents_bp.route("/delete/<int:document_id>", methods=["POST"])
@require_permission("delete_document")
def delete(document_id):
    if not _is_logged_in():
        return redirect(url_for("auth.login"))
    document = db.session.scalar(
        db.select(Document).where(
            Document.id == document_id, Document.user_id == session["user_id"]
        )
    )
    if document:
        mark_document_deleted(document)
    return redirect(url_for("documents.index"))


@documents_bp.route("/favorite/<int:document_id>", methods=["POST"])
@require_permission("edit_document")
def favorite_document(document_id):
    if not _is_logged_in():
        return redirect(url_for("auth.login"))
    document = db.session.scalar(
        db.select(Document).where(
            Document.id == document_id,
            Document.user_id == session["user_id"],
            Document.is_deleted.is_(False),
        )
    )
    if document:
        document.is_favorite = not document.is_favorite
        db.session.commit()
    return redirect(url_for("documents.index", view=request.form.get("view", "mine")))


@documents_bp.route("/restore/<int:document_id>", methods=["POST"])
@require_permission("delete_document")
def restore_document(document_id):
    if not _is_logged_in():
        return redirect(url_for("auth.login"))
    document = db.session.scalar(
        db.select(Document).where(
            Document.id == document_id,
            Document.user_id == session["user_id"],
            Document.is_deleted.is_(True),
        )
    )
    if document:
        restore_document_record(document)
    return redirect(url_for("documents.index", view="deleted"))
