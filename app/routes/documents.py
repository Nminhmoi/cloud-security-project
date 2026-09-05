from flask import Blueprint, redirect, render_template, request, session, url_for

from database import get_db_connection
from services.storage_service import save_upload, send_stored_file

documents_bp = Blueprint("documents", __name__)


def _is_logged_in():
    return "user_id" in session


def _current_role_name(connection):
    user = connection.execute(
        """SELECT r.name AS role_name
           FROM users u
           LEFT JOIN roles r ON r.id = u.role_id
           WHERE u.id = ?""",
        (session["user_id"],),
    ).fetchone()
    return user["role_name"] if user else None


@documents_bp.route("/")
def home():
    if not _is_logged_in():
        return render_template("home.html")

    connection = get_db_connection()
    role_name = _current_role_name(connection)
    connection.close()

    if role_name == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("documents.index"))


@documents_bp.route("/documents")
def index():
    if not _is_logged_in():
        return redirect(url_for("auth.login"))

    connection = get_db_connection()
    if _current_role_name(connection) == "admin":
        connection.close()
        return redirect(url_for("admin.dashboard"))

    documents = connection.execute(
        "SELECT * FROM documents WHERE user_id = ? AND is_deleted = 0",
        (session["user_id"],),
    ).fetchall()
    shared_documents = connection.execute(
        """
        SELECT documents.*, users.username AS owner
        FROM documents
        JOIN document_shares
            ON documents.id = document_shares.document_id
        JOIN users
            ON documents.user_id = users.id
        WHERE document_shares.shared_with_user_id = ?
          AND documents.is_deleted = 0
        """,
        (session["user_id"],),
    ).fetchall()
    deleted_documents = connection.execute(
        "SELECT * FROM documents WHERE user_id = ? AND is_deleted = 1",
        (session["user_id"],),
    ).fetchall()
    connection.close()

    return render_template(
        "index.html",
        documents=documents,
        shared_documents=shared_documents,
        deleted_documents=deleted_documents,
        active_view=request.args.get("view", "mine"),
    )


@documents_bp.route("/upload", methods=["POST"])
def upload():
    if not _is_logged_in():
        return redirect(url_for("auth.login"))

    file = request.files.get("file")
    if not file or not file.filename:
        return "Chưa chọn file!", 400

    filename = save_upload(file, session["user_id"])
    file_size = file.content_length
    if not file_size:
        file.stream.seek(0, 2)
        file_size = file.stream.tell()
    connection = get_db_connection()
    connection.execute(
        "INSERT INTO documents (filename, user_id, file_size, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        (filename, session["user_id"], file_size or 0),
    )
    connection.commit()
    connection.close()
    return redirect(url_for("documents.index", uploaded=filename))


@documents_bp.route("/download/<int:document_id>")
def download(document_id):
    if not _is_logged_in():
        return redirect(url_for("auth.login"))

    connection = get_db_connection()
    document = connection.execute(
        """
        SELECT documents.*
        FROM documents
        LEFT JOIN document_shares
            ON documents.id = document_shares.document_id
        WHERE documents.id = ?
          AND documents.is_deleted = 0
          AND (
              documents.user_id = ?
              OR document_shares.shared_with_user_id = ?
          )
        """,
        (document_id, session["user_id"], session["user_id"]),
    ).fetchone()
    connection.close()

    if not document:
        return "Bạn không có quyền truy cập tài liệu này!", 403

    return send_stored_file(document["filename"])


@documents_bp.route("/delete/<int:document_id>", methods=["POST"])
def delete(document_id):
    if not _is_logged_in():
        return redirect(url_for("auth.login"))

    connection = get_db_connection()
    connection.execute(
        "UPDATE documents SET is_deleted = 1 WHERE id = ? AND user_id = ?",
        (document_id, session["user_id"]),
    )
    connection.commit()
    connection.close()
    return redirect(url_for("documents.index"))


@documents_bp.route("/favorite/<int:document_id>", methods=["POST"])
def favorite_document(document_id):
    if not _is_logged_in():
        return redirect(url_for("auth.login"))

    connection = get_db_connection()
    connection.execute(
        """
        UPDATE documents
        SET is_favorite = CASE is_favorite WHEN 1 THEN 0 ELSE 1 END
        WHERE id = ? AND user_id = ? AND is_deleted = 0
        """,
        (document_id, session["user_id"]),
    )
    connection.commit()
    connection.close()
    return redirect(
        url_for("documents.index", view=request.form.get("view", "mine"))
    )


@documents_bp.route("/restore/<int:document_id>", methods=["POST"])
def restore_document(document_id):
    if not _is_logged_in():
        return redirect(url_for("auth.login"))

    connection = get_db_connection()
    connection.execute(
        "UPDATE documents SET is_deleted = 0 WHERE id = ? AND user_id = ?",
        (document_id, session["user_id"]),
    )
    connection.commit()
    connection.close()
    return redirect(url_for("documents.index", view="deleted"))
