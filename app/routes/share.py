"""Browser routes for document sharing."""

from flask import Blueprint, jsonify, redirect, request, session, url_for
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Document, DocumentShare, User

share_bp = Blueprint("share", __name__)


@share_bp.route("/search-users")
def search_users():
    if "user_id" not in session:
        return jsonify(users=[]), 401

    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify(users=[])

    term = f"%{query.casefold()}%"
    users = db.session.scalars(
        db.select(User)
        .where(
            User.id != session["user_id"],
            User.is_active.is_(True),
            or_(
                func.lower(User.username).like(term),
                func.lower(User.email).like(term),
            ),
        )
        .order_by(User.username)
        .limit(8)
    ).all()
    return jsonify(
        users=[{"id": user.id, "username": user.username, "email": user.email} for user in users]
    )


@share_bp.route("/share/<int:document_id>", methods=["POST"])
def share_document(document_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    document = db.session.scalar(
        db.select(Document).where(
            Document.id == document_id,
            Document.user_id == session["user_id"],
            Document.is_deleted.is_(False),
        )
    )
    if not document:
        return "Bạn không có quyền chia sẻ tài liệu này!", 403

    recipient = request.form.get("recipient", "").strip()
    normalized_recipient = recipient.casefold()
    user = db.session.scalar(
        db.select(User).where(
            User.is_active.is_(True),
            or_(
                func.lower(User.username) == normalized_recipient,
                func.lower(User.email) == normalized_recipient,
            ),
        )
    )
    if not user:
        return "Không tìm thấy người dùng!", 404
    if user.id == session["user_id"]:
        return "Không thể chia sẻ tài liệu cho chính mình!", 400

    try:
        db.session.add(
            DocumentShare(document_id=document_id, shared_with_user_id=user.id)
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return "Tài liệu đã được chia sẻ cho người dùng này!", 409
    return redirect(url_for("documents.index"))


@share_bp.route("/unshare/<int:document_id>/<int:user_id>", methods=["POST"])
def unshare_document(document_id, user_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    share = db.session.scalar(
        db.select(DocumentShare)
        .join(Document)
        .where(
            DocumentShare.document_id == document_id,
            DocumentShare.shared_with_user_id == user_id,
            Document.user_id == session["user_id"],
        )
    )
    if share:
        db.session.delete(share)
        db.session.commit()
    return redirect(url_for("documents.index"))
