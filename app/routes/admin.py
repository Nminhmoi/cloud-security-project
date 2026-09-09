"""Admin routes for managing users, roles, and permissions."""

from flask import Blueprint, current_app, jsonify, render_template, request, session
from sqlalchemy import func

from extensions import db
from models import ActivityLog, Document, Permission, Role, User
from permissions import (
    get_all_permissions,
    get_all_roles,
    get_role_permissions,
    require_admin,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _json_id(field_name):
    data = request.get_json(silent=True) or {}
    value = data.get(field_name)
    if isinstance(value, bool):
        return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _is_last_active_admin(user_id):
    user = db.session.get(User, user_id)
    if not user or user.role_name != "admin" or not user.is_active:
        return False
    active_admins = db.session.scalar(
        db.select(func.count(User.id))
        .join(Role)
        .where(Role.name == "admin", User.is_active.is_(True))
    )
    return active_admins <= 1


@admin_bp.route("/dashboard")
@require_admin
def dashboard():
    total_users = db.session.scalar(db.select(func.count(User.id)))
    admin_count = db.session.scalar(
        db.select(func.count(User.id)).join(Role).where(Role.name == "admin")
    )
    user_count = db.session.scalar(
        db.select(func.count(User.id)).join(Role).where(Role.name == "user")
    )
    total_documents = db.session.scalar(
        db.select(func.count(Document.id)).where(Document.is_deleted.is_(False))
    )
    return render_template(
        "admin/dashboard.html",
        stats={
            "total_users": total_users,
            "admin_count": admin_count,
            "user_count": user_count,
            "total_documents": total_documents,
        },
    )


@admin_bp.route("/documents")
@require_admin
def documents_list():
    documents = db.session.scalars(
        db.select(Document).order_by(Document.created_at.desc(), Document.id.desc())
    ).all()
    return render_template(
        "admin/documents.html",
        documents=[document.to_dict(include_owner=True) for document in documents],
    )


@admin_bp.route("/documents/<int:document_id>/delete", methods=["POST"])
@require_admin
def delete_document(document_id):
    document = db.session.get(Document, document_id)
    if not document:
        return jsonify({"error": "Tài liệu không tồn tại"}), 404
    if document.is_deleted:
        return jsonify({"error": "Tài liệu đã bị xóa trước đó"}), 400

    document.is_deleted = True
    db.session.add(
        ActivityLog(
            actor_user_id=session.get("user_id"),
            action="delete_document",
            target_type="document",
            target_id=document_id,
            details=f"Xóa tài liệu {document.filename} của người dùng #{document.user_id}",
        )
    )
    db.session.commit()
    return jsonify({"success": "Đã xóa tài liệu khỏi hệ thống"})


@admin_bp.route("/activity-logs")
@require_admin
def activity_logs():
    logs = db.session.scalars(
        db.select(ActivityLog)
        .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
        .limit(500)
    ).all()
    return render_template(
        "admin/activity_logs.html", logs=[log.to_dict() for log in logs]
    )


@admin_bp.route("/users")
@require_admin
def users_list():
    users = db.session.scalars(db.select(User).order_by(User.id)).all()
    return render_template(
        "admin/users.html",
        users=[user.to_dict(include_role=True) for user in users],
        roles=get_all_roles(),
    )


@admin_bp.route("/users/<int:user_id>", methods=["GET"])
@require_admin
def get_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "Người dùng không tồn tại"}), 404
    return jsonify(user.to_dict(include_role=True))


@admin_bp.route("/users/<int:user_id>/role", methods=["POST"])
@require_admin
def change_user_role(user_id):
    role_id = _json_id("role_id")
    if role_id is None:
        return jsonify({"error": "role_id không hợp lệ"}), 400
    if user_id == session.get("user_id"):
        return jsonify({"error": "Không thể thay đổi vai trò của chính mình"}), 400

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "Người dùng không tồn tại"}), 404
    role = db.session.get(Role, role_id)
    if not role:
        return jsonify({"error": "Vai trò không tồn tại"}), 404
    if role.name != "admin" and _is_last_active_admin(user_id):
        return jsonify({"error": "Không thể hạ quyền admin đang hoạt động cuối cùng"}), 400

    previous_role = user.role_name or "unassigned"
    user.role = role
    db.session.add(
        ActivityLog(
            actor_user_id=session.get("user_id"),
            action="change_user_role",
            target_type="user",
            target_id=user_id,
            details=f"Changed role from {previous_role} to {role.name}",
        )
    )
    db.session.commit()
    return jsonify({"success": "Đổi vai trò thành công"})


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@require_admin
def toggle_user_active(user_id):
    if user_id == session.get("user_id"):
        return jsonify({"error": "Không thể vô hiệu hóa tài khoản của chính mình"}), 400

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "Người dùng không tồn tại"}), 404
    if user.is_active and _is_last_active_admin(user_id):
        return jsonify({"error": "Không thể vô hiệu hóa admin đang hoạt động cuối cùng"}), 400

    user.is_active = not user.is_active
    action = "enable_user" if user.is_active else "disable_user"
    status_label = "kích hoạt" if user.is_active else "vô hiệu hóa"
    db.session.add(
        ActivityLog(
            actor_user_id=session.get("user_id"),
            action=action,
            target_type="user",
            target_id=user_id,
            details=(
                f"Đã {status_label} tài khoản {user.username} "
                f"({user.email or 'không có email'})"
            ),
        )
    )
    db.session.commit()
    return jsonify(
        {"success": "Cập nhật trạng thái thành công", "is_active": int(user.is_active)}
    )


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@require_admin
def delete_user(user_id):
    if user_id == session.get("user_id"):
        return jsonify({"error": "Không thể xóa tài khoản của chính mình"}), 400

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "Người dùng không tồn tại"}), 404
    if _is_last_active_admin(user_id):
        return jsonify({"error": "Không thể xóa admin đang hoạt động cuối cùng"}), 400

    identity = (
        f"Đã xóa tài khoản {user.username} ({user.email or 'không có email'}), "
        f"vai trò {user.role_name or 'chưa gán'}"
    )
    try:
        db.session.add(
            ActivityLog(
                actor_user_id=session.get("user_id"),
                action="delete_user",
                target_type="user",
                target_id=user_id,
                details=identity,
            )
        )
        db.session.delete(user)
        db.session.commit()
        return jsonify({"success": "Xóa người dùng thành công"})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to delete user %s", user_id)
        return jsonify({"error": "Không thể xóa người dùng"}), 500


@admin_bp.route("/roles")
@require_admin
def roles_list():
    roles = get_all_roles()
    for role in roles:
        role["permissions"] = get_role_permissions(role["id"])
    return render_template(
        "admin/roles.html", roles=roles, permissions=get_all_permissions()
    )


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
    role = db.session.get(Role, role_id)
    permission = db.session.get(Permission, permission_id)
    if not role or not permission or permission in role.permissions:
        return jsonify({"error": "Không thể gán quyền"}), 400
    role.permissions.append(permission)
    db.session.add(
        ActivityLog(
            actor_user_id=session.get("user_id"),
            action="assign_role_permission",
            target_type="role",
            target_id=role_id,
            details=f"Assigned permission {permission.name}",
        )
    )
    db.session.commit()
    return jsonify({"success": "Gán quyền thành công"})


@admin_bp.route("/roles/<int:role_id>/revoke-permission", methods=["POST"])
@require_admin
def revoke_permission(role_id):
    permission_id = _json_id("permission_id")
    if permission_id is None:
        return jsonify({"error": "permission_id không hợp lệ"}), 400
    role = db.session.get(Role, role_id)
    permission = db.session.get(Permission, permission_id)
    if not role or not permission or permission not in role.permissions:
        return jsonify({"error": "Không thể thu hồi quyền"}), 400
    role.permissions.remove(permission)
    db.session.add(
        ActivityLog(
            actor_user_id=session.get("user_id"),
            action="revoke_role_permission",
            target_type="role",
            target_id=role_id,
            details=f"Revoked permission {permission.name}",
        )
    )
    db.session.commit()
    return jsonify({"success": "Thu hồi quyền thành công"})


@admin_bp.route("/permissions")
@require_admin
def permissions_list():
    return render_template(
        "admin/permissions.html", permissions=get_all_permissions()
    )
