"""JSON REST API for authentication, documents, and document sharing."""

import re
import sqlite3
from functools import wraps

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db_connection
from routes.auth import _valid_username
from services.storage_service import save_upload, send_stored_file

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


def _document_dict(row, access="owner"):
    document = dict(row)
    document["is_favorite"] = bool(document.get("is_favorite"))
    document["is_deleted"] = bool(document.get("is_deleted"))
    document["access"] = access
    return document


@api_bp.post("/auth/register")
def register():
    data = _json_body()
    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")
    if not _valid_username(username):
        return _error("Tên đăng nhập phải dài 6-24 ký tự, gồm chữ, số và ký tự đặc biệt", 400)
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return _error("Địa chỉ email không hợp lệ", 400)
    if not isinstance(password, str) or len(password) < 6:
        return _error("Mật khẩu phải có ít nhất 6 ký tự", 400)
    connection = get_db_connection()
    try:
        cursor = connection.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (username, email, generate_password_hash(password)),
        )
        connection.commit()
        return jsonify({"data": {"id": cursor.lastrowid, "username": username, "email": email}}), 201
    except sqlite3.IntegrityError:
        return _error("Tên đăng nhập hoặc email đã tồn tại", 409)
    finally:
        connection.close()


@api_bp.post("/auth/login")
def login():
    data = _json_body()
    username = str(data.get("username", "")).strip()
    password = data.get("password", "")
    connection = get_db_connection()
    user = connection.execute(
        """SELECT u.id, u.username, u.email, u.password, u.is_active, r.name AS role
           FROM users u LEFT JOIN roles r ON r.id = u.role_id WHERE u.username = ?""",
        (username,),
    ).fetchone()
    connection.close()
    if not user or not isinstance(password, str) or not check_password_hash(user["password"], password):
        return _error("Tên đăng nhập hoặc mật khẩu không đúng", 401)
    if not user["is_active"]:
        return _error("Tài khoản đã bị vô hiệu hóa", 403)
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return jsonify({"data": {"id": user["id"], "username": user["username"], "email": user["email"], "role": user["role"]}})


@api_bp.post("/auth/logout")
@api_login_required
def logout():
    session.clear()
    return jsonify({"data": {"message": "Đăng xuất thành công"}})


@api_bp.get("/me")
@api_login_required
def me():
    connection = get_db_connection()
    user = connection.execute(
        """SELECT u.id, u.username, u.email, u.is_active, r.name AS role
           FROM users u LEFT JOIN roles r ON r.id = u.role_id WHERE u.id = ?""",
        (session["user_id"],),
    ).fetchone()
    connection.close()
    if not user:
        session.clear()
        return _error("Tài khoản không tồn tại", 401)
    data = dict(user)
    data["is_active"] = bool(data["is_active"])
    return jsonify({"data": data})


@api_bp.get("/documents")
@api_login_required
def list_documents():
    view = request.args.get("view", "mine")
    connection = get_db_connection()
    if view == "shared":
        rows = connection.execute(
            """SELECT d.id, d.filename, d.file_size, d.created_at, d.is_favorite,
                      d.is_deleted, u.id AS owner_id, u.username AS owner_name
               FROM documents d JOIN document_shares s ON s.document_id = d.id
               JOIN users u ON u.id = d.user_id
               WHERE s.shared_with_user_id = ? AND d.is_deleted = 0
               ORDER BY d.created_at DESC, d.id DESC""", (session["user_id"],)
        ).fetchall()
        access = "shared"
    elif view in ("mine", "deleted"):
        rows = connection.execute(
            """SELECT id, filename, file_size, created_at, is_favorite, is_deleted
               FROM documents WHERE user_id = ? AND is_deleted = ?
               ORDER BY created_at DESC, id DESC""",
            (session["user_id"], 1 if view == "deleted" else 0),
        ).fetchall()
        access = "owner"
    else:
        connection.close()
        return _error("view chỉ nhận mine, shared hoặc deleted", 400)
    connection.close()
    return jsonify({"data": [_document_dict(row, access) for row in rows]})


@api_bp.post("/documents")
@api_login_required
def upload_document():
    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return _error("Thiếu file tải lên", 400)
    filename = save_upload(uploaded_file, session["user_id"])
    uploaded_file.stream.seek(0, 2)
    file_size = uploaded_file.stream.tell()
    connection = get_db_connection()
    cursor = connection.execute(
        "INSERT INTO documents (filename, user_id, file_size, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        (filename, session["user_id"], file_size),
    )
    connection.commit()
    row = connection.execute(
        "SELECT id, filename, file_size, created_at, is_favorite, is_deleted FROM documents WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    connection.close()
    return jsonify({"data": _document_dict(row)}), 201


def _accessible_document(document_id):
    connection = get_db_connection()
    row = connection.execute(
        """SELECT DISTINCT d.* FROM documents d LEFT JOIN document_shares s ON s.document_id = d.id
           WHERE d.id = ? AND d.is_deleted = 0
             AND (d.user_id = ? OR s.shared_with_user_id = ?)""",
        (document_id, session["user_id"], session["user_id"]),
    ).fetchone()
    connection.close()
    return row


@api_bp.get("/documents/<int:document_id>/download")
@api_login_required
def download_document(document_id):
    document = _accessible_document(document_id)
    if not document:
        return _error("Không tìm thấy tài liệu hoặc bạn không có quyền truy cập", 404)
    return send_stored_file(document["filename"])


@api_bp.delete("/documents/<int:document_id>")
@api_login_required
def delete_document(document_id):
    connection = get_db_connection()
    cursor = connection.execute(
        "UPDATE documents SET is_deleted = 1 WHERE id = ? AND user_id = ? AND is_deleted = 0",
        (document_id, session["user_id"]),
    )
    connection.commit()
    connection.close()
    if cursor.rowcount == 0:
        return _error("Không tìm thấy tài liệu thuộc sở hữu của bạn", 404)
    return "", 204


@api_bp.post("/documents/<int:document_id>/restore")
@api_login_required
def restore_document(document_id):
    connection = get_db_connection()
    cursor = connection.execute(
        "UPDATE documents SET is_deleted = 0 WHERE id = ? AND user_id = ? AND is_deleted = 1",
        (document_id, session["user_id"]),
    )
    connection.commit()
    connection.close()
    if cursor.rowcount == 0:
        return _error("Không tìm thấy tài liệu đã xóa thuộc sở hữu của bạn", 404)
    return jsonify({"data": {"id": document_id, "is_deleted": False}})


@api_bp.patch("/documents/<int:document_id>/favorite")
@api_login_required
def update_favorite(document_id):
    data = _json_body()
    if not isinstance(data.get("is_favorite"), bool):
        return _error("is_favorite phải là boolean", 400)
    connection = get_db_connection()
    cursor = connection.execute(
        "UPDATE documents SET is_favorite = ? WHERE id = ? AND user_id = ? AND is_deleted = 0",
        (int(data["is_favorite"]), document_id, session["user_id"]),
    )
    connection.commit()
    connection.close()
    if cursor.rowcount == 0:
        return _error("Không tìm thấy tài liệu thuộc sở hữu của bạn", 404)
    return jsonify({"data": {"id": document_id, "is_favorite": data["is_favorite"]}})


@api_bp.get("/users/search")
@api_login_required
def search_users():
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return _error("Từ khóa phải có ít nhất 2 ký tự", 400)
    term = f"%{query}%"
    connection = get_db_connection()
    rows = connection.execute(
        """SELECT id, username, email FROM users WHERE id != ? AND is_active = 1
           AND (username LIKE ? COLLATE NOCASE OR email LIKE ? COLLATE NOCASE)
           ORDER BY username LIMIT 20""", (session["user_id"], term, term)
    ).fetchall()
    connection.close()
    return jsonify({"data": [dict(row) for row in rows]})


@api_bp.get("/documents/<int:document_id>/shares")
@api_login_required
def list_shares(document_id):
    connection = get_db_connection()
    owned = connection.execute("SELECT 1 FROM documents WHERE id = ? AND user_id = ?", (document_id, session["user_id"])).fetchone()
    if not owned:
        connection.close()
        return _error("Không tìm thấy tài liệu thuộc sở hữu của bạn", 404)
    rows = connection.execute(
        """SELECT u.id, u.username, u.email FROM document_shares s
           JOIN users u ON u.id = s.shared_with_user_id
           WHERE s.document_id = ? ORDER BY u.username""", (document_id,)
    ).fetchall()
    connection.close()
    return jsonify({"data": [dict(row) for row in rows]})


@api_bp.post("/documents/<int:document_id>/shares")
@api_login_required
def create_share(document_id):
    recipient = str(_json_body().get("recipient", "")).strip()
    if not recipient:
        return _error("Thiếu recipient (username hoặc email)", 400)
    connection = get_db_connection()
    try:
        owned = connection.execute(
            "SELECT 1 FROM documents WHERE id = ? AND user_id = ? AND is_deleted = 0",
            (document_id, session["user_id"]),
        ).fetchone()
        if not owned:
            return _error("Không tìm thấy tài liệu thuộc sở hữu của bạn", 404)
        user = connection.execute(
            """SELECT id, username, email FROM users WHERE is_active = 1
               AND (username = ? OR email = ? COLLATE NOCASE)""", (recipient, recipient.lower())
        ).fetchone()
        if not user:
            return _error("Không tìm thấy người nhận", 404)
        if user["id"] == session["user_id"]:
            return _error("Không thể chia sẻ tài liệu cho chính mình", 400)
        connection.execute(
            "INSERT INTO document_shares (document_id, shared_with_user_id) VALUES (?, ?)",
            (document_id, user["id"]),
        )
        connection.commit()
        return jsonify({"data": dict(user)}), 201
    except sqlite3.IntegrityError:
        return _error("Tài liệu đã được chia sẻ cho người dùng này", 409)
    finally:
        connection.close()


@api_bp.delete("/documents/<int:document_id>/shares/<int:user_id>")
@api_login_required
def delete_share(document_id, user_id):
    connection = get_db_connection()
    cursor = connection.execute(
        """DELETE FROM document_shares WHERE document_id = ? AND shared_with_user_id = ?
           AND EXISTS (SELECT 1 FROM documents d WHERE d.id = ? AND d.user_id = ?)""",
        (document_id, user_id, document_id, session["user_id"]),
    )
    connection.commit()
    connection.close()
    if cursor.rowcount == 0:
        return _error("Không tìm thấy lượt chia sẻ", 404)
    return "", 204
