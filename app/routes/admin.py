"""Admin routes for managing users, roles, and permissions."""

from flask import Blueprint, current_app, jsonify, render_template, request, session

from database import get_db_connection
from permissions import (
    assign_permission_to_role,
    get_all_permissions,
    get_all_roles,
    get_role_permissions,
    require_admin,
    revoke_permission_from_role,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _json_id(field_name):
    """Return a positive integer from the JSON body, or None when invalid."""
    data = request.get_json(silent=True) or {}
    value = data.get(field_name)
    if isinstance(value, bool):
        return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _is_last_active_admin(connection, user_id):
    user = connection.execute(
        """SELECT u.is_active, r.name AS role_name FROM users u
           LEFT JOIN roles r ON r.id = u.role_id WHERE u.id = ?""",
        (user_id,),
    ).fetchone()
    if not user or user["role_name"] != "admin" or not user["is_active"]:
        return False
    count = connection.execute(
        """SELECT COUNT(*) AS count FROM users u
           JOIN roles r ON r.id = u.role_id
           WHERE r.name = 'admin' AND u.is_active = 1"""
    ).fetchone()["count"]
    return count <= 1


@admin_bp.route("/dashboard")
@require_admin
def dashboard():
    connection = get_db_connection()
    total_users = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
    admin_count = connection.execute(
        """SELECT COUNT(*) AS count FROM users u
           JOIN roles r ON r.id = u.role_id WHERE r.name = 'admin'"""
    ).fetchone()["count"]
    user_count = connection.execute(
        """SELECT COUNT(*) AS count FROM users u
           JOIN roles r ON r.id = u.role_id WHERE r.name = 'user'"""
    ).fetchone()["count"]
    total_documents = connection.execute(
        "SELECT COUNT(*) AS count FROM documents WHERE is_deleted = 0"
    ).fetchone()["count"]
    connection.close()
    return render_template("admin/dashboard.html", stats={
        "total_users": total_users, "admin_count": admin_count,
        "user_count": user_count, "total_documents": total_documents,
    })


@admin_bp.route("/documents")
@require_admin
def documents_list():
    connection = get_db_connection()
    documents = connection.execute(
        """SELECT d.id, d.filename, d.file_size, d.created_at, d.is_deleted,
                  u.id AS owner_id, u.username AS owner_name
           FROM documents d
           JOIN users u ON u.id = d.user_id
           ORDER BY d.created_at DESC, d.id DESC"""
    ).fetchall()
    connection.close()
    return render_template(
        "admin/documents.html", documents=[dict(row) for row in documents]
    )


@admin_bp.route("/documents/<int:document_id>/delete", methods=["POST"])
@require_admin
def delete_document(document_id):
    connection = get_db_connection()
    try:
        document = connection.execute(
            "SELECT id, filename, user_id, is_deleted FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()
        if not document:
            return jsonify({"error": "Tài liệu không tồn tại"}), 404
        if document["is_deleted"]:
            return jsonify({"error": "Tài liệu đã bị xóa trước đó"}), 400
        connection.execute(
            "UPDATE documents SET is_deleted = 1 WHERE id = ?", (document_id,)
        )
        connection.execute(
            """INSERT INTO activity_logs
               (actor_user_id, action, target_type, target_id, details)
               VALUES (?, 'delete_document', 'document', ?, ?)""",
            (
                session.get("user_id"),
                document_id,
                f"Xóa tài liệu {document['filename']} của người dùng #{document['user_id']}",
            ),
        )
        connection.commit()
        return jsonify({"success": "Đã xóa tài liệu khỏi hệ thống"})
    finally:
        connection.close()


@admin_bp.route("/activity-logs")
@require_admin
def activity_logs():
    connection = get_db_connection()
    logs = connection.execute(
        """SELECT l.id, l.action, l.target_type, l.target_id, l.details,
                  l.created_at, COALESCE(u.username, 'Hệ thống') AS actor_name
           FROM activity_logs l
           LEFT JOIN users u ON u.id = l.actor_user_id
           ORDER BY l.created_at DESC, l.id DESC
           LIMIT 500"""
    ).fetchall()
    connection.close()
    return render_template("admin/activity_logs.html", logs=[dict(row) for row in logs])


@admin_bp.route("/users")
@require_admin
def users_list():
    connection = get_db_connection()
    users = connection.execute(
        """SELECT u.id, u.username, u.email, u.is_active, u.role_id,
                  r.name AS role_name
           FROM users u LEFT JOIN roles r ON u.role_id = r.id ORDER BY u.id"""
    ).fetchall()
    connection.close()
    return render_template("admin/users.html", users=[dict(row) for row in users], roles=get_all_roles())


@admin_bp.route("/users/<int:user_id>", methods=["GET"])
@require_admin
def get_user(user_id):
    connection = get_db_connection()
    user = connection.execute(
        """SELECT u.id, u.username, u.email, u.is_active, u.role_id,
                  r.name AS role_name FROM users u
           LEFT JOIN roles r ON u.role_id = r.id WHERE u.id = ?""",
        (user_id,),
    ).fetchone()
    connection.close()
    if not user:
        return jsonify({"error": "Người dùng không tồn tại"}), 404
    return jsonify(dict(user))


@admin_bp.route("/users/<int:user_id>/role", methods=["POST"])
@require_admin
def change_user_role(user_id):
    role_id = _json_id("role_id")
    if role_id is None:
        return jsonify({"error": "role_id không hợp lệ"}), 400
    if user_id == session.get("user_id"):
        return jsonify({"error": "Không thể thay đổi vai trò của chính mình"}), 400
    connection = get_db_connection()
    try:
        if not connection.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone():
            return jsonify({"error": "Người dùng không tồn tại"}), 404
        role = connection.execute("SELECT name FROM roles WHERE id = ?", (role_id,)).fetchone()
        if not role:
            return jsonify({"error": "Vai trò không tồn tại"}), 404
        if role["name"] != "admin" and _is_last_active_admin(connection, user_id):
            return jsonify({"error": "Không thể hạ quyền admin đang hoạt động cuối cùng"}), 400
        connection.execute("UPDATE users SET role_id = ? WHERE id = ?", (role_id, user_id))
        connection.commit()
        return jsonify({"success": "Đổi vai trò thành công"})
    finally:
        connection.close()


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@require_admin
def toggle_user_active(user_id):
    if user_id == session.get("user_id"):
        return jsonify({"error": "Không thể vô hiệu hóa tài khoản của chính mình"}), 400
    connection = get_db_connection()
    try:
        user = connection.execute(
            "SELECT username, email, is_active FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return jsonify({"error": "Người dùng không tồn tại"}), 404
        if user["is_active"] and _is_last_active_admin(connection, user_id):
            return jsonify({"error": "Không thể vô hiệu hóa admin đang hoạt động cuối cùng"}), 400
        new_status = 0 if user["is_active"] else 1
        connection.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
        action = "enable_user" if new_status else "disable_user"
        status_label = "kích hoạt" if new_status else "vô hiệu hóa"
        connection.execute(
            """INSERT INTO activity_logs
               (actor_user_id, action, target_type, target_id, details)
               VALUES (?, ?, 'user', ?, ?)""",
            (
                session.get("user_id"),
                action,
                user_id,
                f"Đã {status_label} tài khoản {user['username']} ({user['email'] or 'không có email'})",
            ),
        )
        connection.commit()
        return jsonify({"success": "Cập nhật trạng thái thành công", "is_active": new_status})
    finally:
        connection.close()


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@require_admin
def delete_user(user_id):
    if user_id == session.get("user_id"):
        return jsonify({"error": "Không thể xóa tài khoản của chính mình"}), 400
    connection = get_db_connection()
    try:
        user = connection.execute(
            """SELECT u.username, u.email, r.name AS role_name
               FROM users u LEFT JOIN roles r ON r.id = u.role_id
               WHERE u.id = ?""",
            (user_id,),
        ).fetchone()
        if not user:
            return jsonify({"error": "Người dùng không tồn tại"}), 404
        if _is_last_active_admin(connection, user_id):
            return jsonify({"error": "Không thể xóa admin đang hoạt động cuối cùng"}), 400
        connection.execute("DELETE FROM document_shares WHERE shared_with_user_id = ?", (user_id,))
        connection.execute(
            "DELETE FROM document_shares WHERE document_id IN (SELECT id FROM documents WHERE user_id = ?)",
            (user_id,),
        )
        connection.execute("DELETE FROM documents WHERE user_id = ?", (user_id,))
        connection.execute(
            """INSERT INTO activity_logs
               (actor_user_id, action, target_type, target_id, details)
               VALUES (?, 'delete_user', 'user', ?, ?)""",
            (
                session.get("user_id"),
                user_id,
                f"Đã xóa tài khoản {user['username']} ({user['email'] or 'không có email'}), vai trò {user['role_name'] or 'chưa gán'}",
            ),
        )
        connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        connection.commit()
        return jsonify({"success": "Xóa người dùng thành công"})
    except Exception:
        connection.rollback()
        current_app.logger.exception("Failed to delete user %s", user_id)
        return jsonify({"error": "Không thể xóa người dùng"}), 500
    finally:
        connection.close()


@admin_bp.route("/roles")
@require_admin
def roles_list():
    roles = get_all_roles()
    for role in roles:
        role["permissions"] = get_role_permissions(role["id"])
    return render_template("admin/roles.html", roles=roles, permissions=get_all_permissions())


@admin_bp.route("/roles/<int:role_id>/permissions", methods=["GET"])
@require_admin
def role_permissions(role_id):
    return jsonify(get_role_permissions(role_id))


@admin_bp.route("/roles/<int:role_id>/assign-permission", methods=["POST"])
@require_admin
def assign_permission(role_id):
    permission_id = _json_id("permission_id")
    if permission_id is None:
        return jsonify({"error": "permission_id không hợp lệ"}), 400
    if assign_permission_to_role(role_id, permission_id):
        return jsonify({"success": "Gán quyền thành công"})
    return jsonify({"error": "Không thể gán quyền"}), 400


@admin_bp.route("/roles/<int:role_id>/revoke-permission", methods=["POST"])
@require_admin
def revoke_permission(role_id):
    permission_id = _json_id("permission_id")
    if permission_id is None:
        return jsonify({"error": "permission_id không hợp lệ"}), 400
    if revoke_permission_from_role(role_id, permission_id):
        return jsonify({"success": "Thu hồi quyền thành công"})
    return jsonify({"error": "Không thể thu hồi quyền"}), 400


@admin_bp.route("/permissions")
@require_admin
def permissions_list():
    return render_template("admin/permissions.html", permissions=get_all_permissions())
