"""JSON REST API for authentication, documents, and document sharing."""

import re
from functools import wraps

from flask import Blueprint, jsonify, request, session
from flask_wtf.csrf import generate_csrf
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from extensions import db, limiter
from models import Document, DocumentShare, User
from routes.auth import _valid_username
from services.auth_service import (
    authenticate_user,
    establish_session,
    password_policy_error,
)
from services.storage_service import save_upload, send_stored_file, validate_upload

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


def _error(message, status):
    return jsonify({"error": {"message": message, "status": status}}), status


def api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return _error("Bạn cần đăng nhập", 401)
        return view(*args, **kwargs)

    return wrapped


def _json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _document_dict(document, access="owner"):
    data = document.to_dict(include_owner=access == "shared")
    data["access"] = access
    return data


@api_bp.post("/auth/register")
@limiter.limit("5 per hour")
def register():
    data = _json_body()
    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")
    if not _valid_username(username):
        return _error(
            "Tên đăng nhập phải dài 6-24 ký tự, gồm chữ, số và ký tự đặc biệt",
            400,
        )
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return _error("Địa chỉ email không hợp lệ", 400)
    password_error = password_policy_error(password)
    if password_error:
        return _error(password_error, 400)

    try:
        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("Tên đăng nhập hoặc email đã tồn tại", 409)
    return jsonify({"data": {"id": user.id, "username": username, "email": email}}), 201


@api_bp.post("/auth/login")
@limiter.limit("5 per minute")
def login():
    data = _json_body()
    identifier = str(data.get("username", "")).strip().casefold()
    password = data.get("password", "")
    result = authenticate_user(identifier, password)
    if result.status == "locked":
        return _error("Quá nhiều lần đăng nhập sai. Vui lòng thử lại sau", 429)
    if result.status == "invalid":
        return _error("Tên đăng nhập hoặc mật khẩu không đúng", 401)
    if result.status == "inactive":
        return _error("Tài khoản đã bị vô hiệu hóa", 403)

    user = result.user
    establish_session(user)
    return jsonify(
        {
            "data": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role_name,
            }
        }
    )


@api_bp.post("/auth/logout")
@api_login_required
def logout():
    session.clear()
    return jsonify({"data": {"message": "Đăng xuất thành công"}})


@api_bp.get("/csrf-token")
@limiter.limit("30 per minute")
def csrf_token():
    return jsonify({"data": {"csrf_token": generate_csrf()}})


@api_bp.get("/me")
@api_login_required
def me():
    user = db.session.get(User, session["user_id"])
    if not user:
        session.clear()
        return _error("Tài khoản không tồn tại", 401)
    return jsonify({"data": user.to_dict(include_role=True)})


@api_bp.get("/documents")
@api_login_required
def list_documents():
    view = request.args.get("view", "mine")
    if view == "shared":
        documents = db.session.scalars(
            db.select(Document)
            .join(DocumentShare)
            .where(
                DocumentShare.shared_with_user_id == session["user_id"],
                Document.is_deleted.is_(False),
            )
            .order_by(Document.created_at.desc(), Document.id.desc())
        ).all()
        access = "shared"
    elif view in ("mine", "deleted"):
        documents = db.session.scalars(
            db.select(Document)
            .where(
                Document.user_id == session["user_id"],
                Document.is_deleted.is_(view == "deleted"),
            )
            .order_by(Document.created_at.desc(), Document.id.desc())
        ).all()
        access = "owner"
    else:
        return _error("view chỉ nhận mine, shared hoặc deleted", 400)
    return jsonify({"data": [_document_dict(item, access) for item in documents]})


@api_bp.post("/documents")
@api_login_required
@limiter.limit("10 per minute")
def upload_document():
    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return _error("Thiếu file tải lên", 400)

    try:
        file_size = validate_upload(uploaded_file)
    except ValueError as error:
        return _error(str(error), 400)
    filename = save_upload(uploaded_file, session["user_id"])
    document = Document(
        filename=filename,
        user_id=session["user_id"],
        file_size=file_size,
    )
    db.session.add(document)
    db.session.commit()
    return jsonify({"data": _document_dict(document)}), 201


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


@api_bp.get("/documents/<int:document_id>/download")
@api_login_required
def download_document(document_id):
    document = _accessible_document(document_id)
    if not document:
        return _error("Không tìm thấy tài liệu hoặc bạn không có quyền truy cập", 404)
    return send_stored_file(document.filename)


@api_bp.delete("/documents/<int:document_id>")
@api_login_required
def delete_document(document_id):
    document = db.session.scalar(
        db.select(Document).where(
            Document.id == document_id,
            Document.user_id == session["user_id"],
            Document.is_deleted.is_(False),
        )
    )
    if not document:
        return _error("Không tìm thấy tài liệu thuộc sở hữu của bạn", 404)
    document.is_deleted = True
    db.session.commit()
    return "", 204


@api_bp.post("/documents/<int:document_id>/restore")
@api_login_required
def restore_document(document_id):
    document = db.session.scalar(
        db.select(Document).where(
            Document.id == document_id,
            Document.user_id == session["user_id"],
            Document.is_deleted.is_(True),
        )
    )
    if not document:
        return _error("Không tìm thấy tài liệu đã xóa thuộc sở hữu của bạn", 404)
    document.is_deleted = False
    db.session.commit()
    return jsonify({"data": {"id": document_id, "is_deleted": False}})


@api_bp.patch("/documents/<int:document_id>/favorite")
@api_login_required
def update_favorite(document_id):
    data = _json_body()
    if not isinstance(data.get("is_favorite"), bool):
        return _error("is_favorite phải là boolean", 400)
    document = db.session.scalar(
        db.select(Document).where(
            Document.id == document_id,
            Document.user_id == session["user_id"],
            Document.is_deleted.is_(False),
        )
    )
    if not document:
        return _error("Không tìm thấy tài liệu thuộc sở hữu của bạn", 404)
    document.is_favorite = data["is_favorite"]
    db.session.commit()
    return jsonify(
        {"data": {"id": document_id, "is_favorite": document.is_favorite}}
    )


@api_bp.get("/users/search")
@api_login_required
@limiter.limit("30 per minute")
def search_users():
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return _error("Từ khóa phải có ít nhất 2 ký tự", 400)
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
        .limit(20)
    ).all()
    return jsonify(
        {
            "data": [
                {"id": user.id, "username": user.username, "email": user.email}
                for user in users
            ]
        }
    )


@api_bp.get("/documents/<int:document_id>/shares")
@api_login_required
def list_shares(document_id):
    document = db.session.scalar(
        db.select(Document).where(
            Document.id == document_id, Document.user_id == session["user_id"]
        )
    )
    if not document:
        return _error("Không tìm thấy tài liệu thuộc sở hữu của bạn", 404)
    users = [share.recipient for share in document.shares]
    users.sort(key=lambda user: user.username)
    return jsonify(
        {
            "data": [
                {"id": user.id, "username": user.username, "email": user.email}
                for user in users
            ]
        }
    )


@api_bp.post("/documents/<int:document_id>/shares")
@api_login_required
def create_share(document_id):
    recipient = str(_json_body().get("recipient", "")).strip()
    if not recipient:
        return _error("Thiếu recipient (username hoặc email)", 400)

    document = db.session.scalar(
        db.select(Document).where(
            Document.id == document_id,
            Document.user_id == session["user_id"],
            Document.is_deleted.is_(False),
        )
    )
    if not document:
        return _error("Không tìm thấy tài liệu thuộc sở hữu của bạn", 404)

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
        return _error("Không tìm thấy người nhận", 404)
    if user.id == session["user_id"]:
        return _error("Không thể chia sẻ tài liệu cho chính mình", 400)

    try:
        db.session.add(
            DocumentShare(document_id=document_id, shared_with_user_id=user.id)
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("Tài liệu đã được chia sẻ cho người dùng này", 409)
    return jsonify(
        {"data": {"id": user.id, "username": user.username, "email": user.email}}
    ), 201


@api_bp.delete("/documents/<int:document_id>/shares/<int:user_id>")
@api_login_required
def delete_share(document_id, user_id):
    share = db.session.scalar(
        db.select(DocumentShare)
        .join(Document)
        .where(
            DocumentShare.document_id == document_id,
            DocumentShare.shared_with_user_id == user_id,
            Document.user_id == session["user_id"],
        )
    )
    if not share:
        return _error("Không tìm thấy lượt chia sẻ", 404)
    db.session.delete(share)
    db.session.commit()
    return "", 204
