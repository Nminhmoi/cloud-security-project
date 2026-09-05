#!/usr/bin/env python3
"""Command-line administrator management for CloudBox."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from app import app
from extensions import db
from models import Role, User


class AdminManager:
    def __init__(self):
        self.app = app

    def create_admin(self, username, email, password):
        with self.app.app_context():
            try:
                if db.session.scalar(
                    db.select(User.id).where(User.username == username)
                ):
                    return False, f"Username '{username}' đã tồn tại!"
                if email and db.session.scalar(
                    db.select(User.id).where(User.email == email)
                ):
                    return False, f"Email '{email}' đã được sử dụng!"

                user = User(
                    username=username,
                    email=email,
                    password=generate_password_hash(password),
                    role_id=1,
                    is_active=True,
                )
                db.session.add(user)
                db.session.commit()
                return True, f"Admin '{username}' tạo thành công! (ID: {user.id})"
            except IntegrityError as error:
                db.session.rollback()
                return False, f"Lỗi: {error}"

    def list_admins(self):
        with self.app.app_context():
            try:
                admins = db.session.scalars(
                    db.select(User)
                    .join(Role)
                    .where(Role.name == "admin")
                    .order_by(User.id)
                ).all()
                if not admins:
                    return [], "Chưa có admin nào"
                return [
                    {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "is_active": int(user.is_active),
                        "role": user.role_name,
                    }
                    for user in admins
                ], "OK"
            except Exception as error:
                return [], f"Lỗi: {error}"

    def change_password(self, user_id, new_password):
        with self.app.app_context():
            try:
                user = db.session.get(User, user_id)
                if not user:
                    return False, "Người dùng không tồn tại!"
                user.password = generate_password_hash(new_password)
                db.session.commit()
                return True, "Mật khẩu đã được cập nhật!"
            except Exception as error:
                db.session.rollback()
                return False, f"Lỗi: {error}"

    def delete_admin(self, user_id):
        with self.app.app_context():
            try:
                admin_count = db.session.scalar(
                    db.select(func.count(User.id))
                    .join(Role)
                    .where(Role.name == "admin")
                )
                if admin_count <= 1:
                    return False, "Không thể xóa admin cuối cùng!"
                user = db.session.get(User, user_id)
                if not user or user.role_name != "admin":
                    return False, "Admin không tồn tại!"
                db.session.delete(user)
                db.session.commit()
                return True, "Admin đã được xóa!"
            except Exception as error:
                db.session.rollback()
                return False, f"Lỗi: {error}"

    def toggle_admin_status(self, user_id):
        with self.app.app_context():
            try:
                user = db.session.get(User, user_id)
                if not user or user.role_name != "admin":
                    return False, "Admin không tồn tại!"
                user.is_active = not user.is_active
                db.session.commit()
                status = "Hoạt động" if user.is_active else "Không hoạt động"
                return True, f"Trạng thái đã cập nhật: {status}"
            except Exception as error:
                db.session.rollback()
                return False, f"Lỗi: {error}"


def _read_user_id():
    try:
        return int(input("ID admin: ").strip())
    except ValueError:
        print("ID phải là số nguyên.")
        return None


def _show_admins(manager):
    admins, message = manager.list_admins()
    if not admins:
        print(message)
        return
    print("\nID  Username                 Email                         Trạng thái")
    print("-" * 75)
    for admin in admins:
        state = "Hoạt động" if admin["is_active"] else "Đã khóa"
        print(
            f"{admin['id']:<3} {admin['username']:<24} "
            f"{(admin['email'] or '-'):<29} {state}"
        )


def main():
    manager = AdminManager()
    while True:
        print(
            "\nCloudBox Admin\n"
            "1. Tạo admin\n"
            "2. Danh sách admin\n"
            "3. Đổi mật khẩu\n"
            "4. Bật/tắt tài khoản\n"
            "5. Xóa admin\n"
            "6. Thoát"
        )
        choice = input("Lựa chọn: ").strip()
        if choice == "1":
            username = input("Username: ").strip()
            email = input("Email: ").strip().lower()
            password = input("Password: ").strip()
            if len(password) < 6:
                print("Mật khẩu phải có ít nhất 6 ký tự.")
                continue
            print(manager.create_admin(username, email, password)[1])
        elif choice == "2":
            _show_admins(manager)
        elif choice == "3":
            user_id = _read_user_id()
            if user_id is not None:
                password = input("Mật khẩu mới: ").strip()
                print(manager.change_password(user_id, password)[1])
        elif choice == "4":
            user_id = _read_user_id()
            if user_id is not None:
                print(manager.toggle_admin_status(user_id)[1])
        elif choice == "5":
            user_id = _read_user_id()
            if user_id is not None:
                print(manager.delete_admin(user_id)[1])
        elif choice == "6":
            break
        else:
            print("Lựa chọn không hợp lệ.")


if __name__ == "__main__":
    main()
