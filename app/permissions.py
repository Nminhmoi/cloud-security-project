"""Role-based access control helpers and decorators."""

from functools import wraps

from flask import abort, current_app, jsonify, redirect, request, session, url_for
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Permission, Role, User


def get_user_role(user_id):
    user = db.session.get(User, user_id)
    return user.role_id if user else None


def get_user_permissions(user_id):
    user = db.session.get(User, user_id)
    if not user or not user.role:
        return []
    return [permission.name for permission in user.role.permissions]


def get_role_name(user_id):
    user = db.session.get(User, user_id)
    return user.role_name if user else None


def has_permission(user_id, permission_name):
    return permission_name in get_user_permissions(user_id)


def has_role(user_id, role_name):
    return get_role_name(user_id) == role_name


def is_admin(user_id):
    return has_role(user_id, "admin")


def _is_api_request():
    return current_app.config.get("API_MODE") or request.path.startswith("/api/")


def _api_error(message, status):
    return jsonify({"error": {"message": message, "status": status}}), status


def require_login(view):
    @wraps(view)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if _is_api_request():
                return _api_error("Vui lòng đăng nhập", 401)
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return decorated_function


def require_permission(permission_name):
    def decorator(view):
        @wraps(view)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                if _is_api_request():
                    return _api_error("Vui lòng đăng nhập", 401)
                return redirect(url_for("auth.login"))
            if not has_permission(session["user_id"], permission_name):
                if _is_api_request():
                    return _api_error("Bạn không có quyền truy cập", 403)
                abort(403)
            return view(*args, **kwargs)

        return decorated_function

    return decorator


def require_role(role_name):
    def decorator(view):
        @wraps(view)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                if _is_api_request():
                    return _api_error("Vui lòng đăng nhập", 401)
                return redirect(url_for("auth.login"))
            if not has_role(session["user_id"], role_name):
                if current_app.config.get("API_MODE"):
                    return jsonify({"error": f"Bạn cần vai trò '{role_name}'"}), 403
                abort(403)
            return view(*args, **kwargs)

        return decorated_function

    return decorator


def require_admin(view):
    return require_role("admin")(view)


def assign_role_to_user(user_id, role_id):
    user = db.session.get(User, user_id)
    role = db.session.get(Role, role_id)
    if not user or not role:
        return False
    try:
        user.role = role
        db.session.commit()
        return True
    except IntegrityError as error:
        db.session.rollback()
        current_app.logger.error("Lỗi gán vai trò: %s", error)
        return False


def get_all_roles():
    roles = db.session.scalars(db.select(Role).order_by(Role.id)).all()
    return [role.to_dict() for role in roles]


def get_all_permissions():
    permissions = db.session.scalars(
        db.select(Permission).order_by(Permission.id)
    ).all()
    return [permission.to_dict() for permission in permissions]


def get_role_permissions(role_id):
    role = db.session.get(Role, role_id)
    if not role:
        return []
    return [permission.to_dict() for permission in sorted(role.permissions, key=lambda p: p.id)]


def create_role(name, description=""):
    try:
        db.session.add(Role(name=name, description=description))
        db.session.commit()
        return True
    except IntegrityError as error:
        db.session.rollback()
        current_app.logger.error("Lỗi tạo vai trò: %s", error)
        return False


def delete_role(role_id):
    if role_id in (1, 2):
        return False
    role = db.session.get(Role, role_id)
    if not role:
        return False
    try:
        db.session.delete(role)
        db.session.commit()
        return True
    except IntegrityError as error:
        db.session.rollback()
        current_app.logger.error("Lỗi xóa vai trò: %s", error)
        return False


def assign_permission_to_role(role_id, permission_id):
    role = db.session.get(Role, role_id)
    permission = db.session.get(Permission, permission_id)
    if not role or not permission:
        return False
    if permission not in role.permissions:
        role.permissions.append(permission)
        db.session.commit()
    return True


def revoke_permission_from_role(role_id, permission_id):
    role = db.session.get(Role, role_id)
    permission = db.session.get(Permission, permission_id)
    if not role or not permission or permission not in role.permissions:
        return False
    role.permissions.remove(permission)
    db.session.commit()
    return True
