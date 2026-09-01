"""
Module quản lý phân quyền (Role-Based Access Control)
"""
from functools import wraps
from flask import session, redirect, url_for, abort, jsonify, current_app
from database import get_db_connection


def get_user_role(user_id):
    """Lấy role của người dùng"""
    connection = get_db_connection()
    user = connection.execute(
        "SELECT role_id FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    connection.close()
    return user["role_id"] if user else None


def get_user_permissions(user_id):
    """Lấy danh sách quyền của người dùng"""
    connection = get_db_connection()
    permissions = connection.execute(
        """
        SELECT p.name FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        JOIN users u ON rp.role_id = u.role_id
        WHERE u.id = ?
        """,
        (user_id,)
    ).fetchall()
    connection.close()
    return [perm["name"] for perm in permissions]


def get_role_name(user_id):
    """Lấy tên role của người dùng"""
    connection = get_db_connection()
    result = connection.execute(
        """
        SELECT r.name FROM roles r
        JOIN users u ON u.role_id = r.id
        WHERE u.id = ?
        """,
        (user_id,)
    ).fetchone()
    connection.close()
    return result["name"] if result else None


def has_permission(user_id, permission_name):
    """Kiểm tra người dùng có quyền cụ thể"""
    permissions = get_user_permissions(user_id)
    return permission_name in permissions


def has_role(user_id, role_name):
    """Kiểm tra người dùng có role cụ thể"""
    role = get_role_name(user_id)
    return role == role_name


def is_admin(user_id):
    """Kiểm tra người dùng có phải admin"""
    return has_role(user_id, "admin")


def require_login(f):
    """Decorator yêu cầu đăng nhập"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if current_app.config.get("API_MODE"):
                return jsonify({"error": "Vui lòng đăng nhập"}), 401
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function


def require_permission(permission_name):
    """Decorator yêu cầu quyền cụ thể"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                if current_app.config.get("API_MODE"):
                    return jsonify({"error": "Vui lòng đăng nhập"}), 401
                return redirect(url_for("auth.login"))
            
            user_id = session.get("user_id")
            if not has_permission(user_id, permission_name):
                if current_app.config.get("API_MODE"):
                    return jsonify({"error": "Bạn không có quyền truy cập"}), 403
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_role(role_name):
    """Decorator yêu cầu role cụ thể"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                if current_app.config.get("API_MODE"):
                    return jsonify({"error": "Vui lòng đăng nhập"}), 401
                return redirect(url_for("auth.login"))
            
            user_id = session.get("user_id")
            if not has_role(user_id, role_name):
                if current_app.config.get("API_MODE"):
                    return jsonify({"error": f"Bạn cần vai trò '{role_name}'"}), 403
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_admin(f):
    """Decorator yêu cầu quyền admin"""
    return require_role("admin")(f)


def assign_role_to_user(user_id, role_id):
    """Gán role cho người dùng"""
    connection = get_db_connection()
    try:
        connection.execute(
            "UPDATE users SET role_id = ? WHERE id = ?",
            (role_id, user_id)
        )
        connection.commit()
        return True
    except Exception as e:
        current_app.logger.error(f"Lỗi gán role: {e}")
        return False
    finally:
        connection.close()


def get_all_roles():
    """Lấy danh sách tất cả roles"""
    connection = get_db_connection()
    roles = connection.execute("SELECT id, name, description FROM roles").fetchall()
    connection.close()
    return [dict(row) for row in roles]


def get_all_permissions():
    """Lấy danh sách tất cả permissions"""
    connection = get_db_connection()
    permissions = connection.execute("SELECT id, name, description FROM permissions").fetchall()
    connection.close()
    return [dict(row) for row in permissions]


def get_role_permissions(role_id):
    """Lấy danh sách quyền của một role"""
    connection = get_db_connection()
    permissions = connection.execute(
        """
        SELECT p.id, p.name, p.description FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        WHERE rp.role_id = ?
        """,
        (role_id,)
    ).fetchall()
    connection.close()
    return [dict(row) for row in permissions]


def create_role(name, description=""):
    """Tạo role mới"""
    connection = get_db_connection()
    try:
        connection.execute(
            "INSERT INTO roles (name, description) VALUES (?, ?)",
            (name, description)
        )
        connection.commit()
        connection.close()
        return True
    except Exception as e:
        current_app.logger.error(f"Lỗi tạo role: {e}")
        return False


def delete_role(role_id):
    """Xóa role (nếu không phải là admin hoặc user)"""
    if role_id in [1, 2]:  # Không xóa admin và user role
        return False
    
    connection = get_db_connection()
    try:
        connection.execute("DELETE FROM roles WHERE id = ?", (role_id,))
        connection.commit()
        connection.close()
        return True
    except Exception as e:
        current_app.logger.error(f"Lỗi xóa role: {e}")
        return False


def assign_permission_to_role(role_id, permission_id):
    """Gán quyền cho role"""
    connection = get_db_connection()
    try:
        connection.execute(
            "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
            (role_id, permission_id)
        )
        connection.commit()
        connection.close()
        return True
    except Exception as e:
        current_app.logger.error(f"Lỗi gán quyền: {e}")
        return False


def revoke_permission_from_role(role_id, permission_id):
    """Thu hồi quyền từ role"""
    connection = get_db_connection()
    try:
        connection.execute(
            "DELETE FROM role_permissions WHERE role_id = ? AND permission_id = ?",
            (role_id, permission_id)
        )
        connection.commit()
        connection.close()
        return True
    except Exception as e:
        current_app.logger.error(f"Lỗi thu hồi quyền: {e}")
        return False
