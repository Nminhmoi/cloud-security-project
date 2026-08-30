import sqlite3

from flask import Blueprint, jsonify, redirect, request, session, url_for

from database import get_db_connection

share_bp = Blueprint("share", __name__)


@share_bp.route("/search-users")
def search_users():
    if "user_id" not in session:
        return jsonify(users=[]), 401

    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify(users=[])

    search_term = f"%{query}%"
    connection = get_db_connection()
    users = connection.execute(
        """
        SELECT id, username, email
        FROM users
        WHERE id != ?
          AND (
              username LIKE ? COLLATE NOCASE
              OR email LIKE ? COLLATE NOCASE
          )
        ORDER BY username
        LIMIT 8
        """,
        (session["user_id"], search_term, search_term),
    ).fetchall()
    connection.close()
    return jsonify(users=[dict(user) for user in users])


@share_bp.route("/share/<int:document_id>", methods=["POST"])
def share_document(document_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    recipient = request.form.get("recipient", "").strip()
    connection = get_db_connection()
    document = connection.execute(
        """
        SELECT id
        FROM documents
        WHERE id = ? AND user_id = ? AND is_deleted = 0
        """,
        (document_id, session["user_id"]),
    ).fetchone()

    if not document:
        connection.close()
        return "Bạn không có quyền chia sẻ tài liệu này!", 403

    user = connection.execute(
        """
        SELECT id
        FROM users
        WHERE username = ? OR email = ? COLLATE NOCASE
        """,
        (recipient, recipient.lower()),
    ).fetchone()

    if not user:
        connection.close()
        return "Không tìm thấy người dùng!", 404

    if user["id"] == session["user_id"]:
        connection.close()
        return "Không thể chia sẻ tài liệu cho chính mình!", 400

    try:
        connection.execute(
            """
            INSERT INTO document_shares (document_id, shared_with_user_id)
            VALUES (?, ?)
            """,
            (document_id, user["id"]),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        return "Tài liệu đã được chia sẻ cho người dùng này!", 409
    finally:
        connection.close()

    return redirect(url_for("documents.index"))


@share_bp.route("/unshare/<int:document_id>/<int:user_id>", methods=["POST"])
def unshare_document(document_id, user_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    connection = get_db_connection()
    connection.execute(
        """
        DELETE FROM document_shares
        WHERE document_id = ?
          AND shared_with_user_id = ?
          AND EXISTS (
              SELECT 1 FROM documents
              WHERE id = ? AND user_id = ?
          )
        """,
        (document_id, user_id, document_id, session["user_id"]),
    )
    connection.commit()
    connection.close()
    return redirect(url_for("documents.index"))
