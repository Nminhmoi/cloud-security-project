#!/usr/bin/env python3
"""
Admin Management Tool - Công Cụ Quản Lý Admin
Tạo, xem, và quản lý tài khoản admin
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Thêm thư mục app vào path để có thể import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app import app
from database import get_db_connection
from werkzeug.security import generate_password_hash
import sqlite3


class AdminManager:
    """Quản lý tài khoản admin"""
    
    def __init__(self):
        self.app = app
    
    def create_admin(self, username, email, password):
        """Tạo tài khoản admin mới"""
        with self.app.app_context():
            conn = None
            try:
                conn = get_db_connection()
                
                # Kiểm tra username
                existing_user = conn.execute(
                    "SELECT id FROM users WHERE username = ?",
                    (username,)
                ).fetchone()
                
                if existing_user:
                    return False, f"❌ Username '{username}' đã tồn tại!"
                
                # Kiểm tra email
                if email:
                    existing_email = conn.execute(
                        "SELECT id FROM users WHERE email = ?",
                        (email,)
                    ).fetchone()
                    
                    if existing_email:
                        return False, f"❌ Email '{email}' đã được sử dụng!"
                
                # Tạo admin
                hashed_pwd = generate_password_hash(password)
                cursor = conn.execute(
                    "INSERT INTO users (username, email, password, role_id, is_active) VALUES (?, ?, ?, ?, ?)",
                    (username, email, hashed_pwd, 1, 1)
                )
                user_id = cursor.lastrowid
                conn.commit()
                conn.close()
                
                return True, f"✅ Admin '{username}' tạo thành công! (ID: {user_id})"
            
            except Exception as e:
                return False, f"❌ Lỗi: {str(e)}"
    
    def list_admins(self):
        """Liệt kê tất cả admin"""
        with self.app.app_context():
            try:
                conn = get_db_connection()
                
                admins = conn.execute(
                    """
                    SELECT u.id, u.username, u.email, u.is_active, r.name as role
                    FROM users u
                    LEFT JOIN roles r ON u.role_id = r.id
                    WHERE r.name = 'admin'
                    ORDER BY u.id
                    """
                ).fetchall()
                
                conn.close()
                
                if not admins:
                    return [], "Chưa có admin nào"
                
                return list(admins), "OK"
            
            except Exception as e:
                return [], f"Lỗi: {str(e)}"
    
    def change_password(self, user_id, new_password):
        """Đổi mật khẩu admin"""
        with self.app.app_context():
            try:
                conn = get_db_connection()
                
                # Kiểm tra user tồn tại
                user = conn.execute(
                    "SELECT id FROM users WHERE id = ?",
                    (user_id,)
                ).fetchone()
                
                if not user:
                    return False, "❌ Người dùng không tồn tại!"
                
                # Đổi mật khẩu
                hashed_pwd = generate_password_hash(new_password)
                conn.execute(
                    "UPDATE users SET password = ? WHERE id = ?",
                    (hashed_pwd, user_id)
                )
                conn.commit()
                conn.close()
                
                return True, "✅ Mật khẩu đã được cập nhật!"
            
            except Exception as e:
                return False, f"❌ Lỗi: {str(e)}"
    
    def delete_admin(self, user_id):
        """Xóa admin (chỉ có thể xóa nếu không phải admin cuối cùng)"""
        with self.app.app_context():
            try:
                conn = get_db_connection()
                
                # Đếm số admin còn lại
                admin_count = conn.execute(
                    """
                    SELECT COUNT(*) as count FROM users u
                    JOIN roles r ON u.role_id = r.id
                    WHERE r.name = 'admin'
                    """
                ).fetchone()['count']
                
                if admin_count <= 1:
                    return False, "❌ Không thể xóa admin cuối cùng!"
                
                # Xóa user
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                conn.close()
                
                return True, "✅ Admin đã được xóa!"
            
            except Exception as e:
                return False, f"❌ Lỗi: {str(e)}"
    
    def toggle_admin_status(self, user_id):
        """Bật/tắt trạng thái admin"""
        with self.app.app_context():
            try:
                conn = get_db_connection()
                
                user = conn.execute(
                    "SELECT is_active FROM users WHERE id = ?",
                    (user_id,)
                ).fetchone()
                
                if not user:
                    return False, "❌ Người dùng không tồn tại!"
                
                new_status = 1 - user['is_active']
                conn.execute(
                    "UPDATE users SET is_active = ? WHERE id = ?",
                    (new_status, user_id)
                )
                conn.commit()
                conn.close()
                
                status_text = "Hoạt động" if new_status else "Không hoạt động"
                return True, f"✅ Trạng thái đã cập nhật: {status_text}"
            
            except Exception as e:
                return False, f"❌ Lỗi: {str(e)}"


def print_banner():
    """In banner"""
    print("\n" + "="*70)
    print("🔐 ADMIN MANAGEMENT TOOL - Công Cụ Quản Lý Admin CloudBox".center(70))
    print("="*70 + "\n")


def print_menu():
    """In menu chính"""
    print("\n📌 MENU CHÍNH:")
    print("   1. ➕ Tạo admin mới")
    print("   2. 📋 Xem danh sách admin")
    print("   3. 🔑 Đổi mật khẩu admin")
    print("   4. ✓ Bật/Tắt trạng thái admin")
    print("   5. 🗑️  Xóa admin")
    print("   6. 🚪 Thoát")
    print()


def create_admin_menu(manager):
    """Menu tạo admin"""
    print("\n" + "="*70)
    print("➕ TẠO ADMIN MỚI".center(70))
    print("="*70)
    
    username = input("\n👤 Username: ").strip()
    if not username:
        print("❌ Username không được để trống!")
        return
    
    email = input("📧 Email: ").strip()
    password = input("🔑 Password: ").strip()
    
    if not password or len(password) < 6:
        print("❌ Password phải ít nhất 6 ký tự!")
        return
    
    success, message = manager.create_admin(username, email, password)
    
    print("\n" + "="*70)
    if success:
        print("✅ TẠO THÀNH CÔNG!".center(70))
        print("="*70)
        print(f"📊 Username: {username}")
        print(f"📧 Email:    {email}")
        print(f"🔑 Password: {password}")
        print(f"🔐 Role:     Admin")
        print("="*70)
        print("\n📌 Truy cập admin:")
        print(f"   🌐 URL: http://localhost:5000/login")
        print(f"   👤 Username: {username}")
        print(f"   🔑 Password: {password}")
    else:
        print("❌ LỖI".center(70))
        print("="*70)
        print(message)
        print("="*70)


def list_admins_menu(manager):
    """Menu xem danh sách admin"""
    print("\n" + "="*70)
    print("📋 DANH SÁCH CÁC ADMIN".center(70))
    print("="*70)
    
    admins, message = manager.list_admins()
    
    if not admins:
        print(f"\n⚠️  {message}")
        return
    
    print(f"\n{'ID':<5} {'Username':<20} {'Email':<25} {'Trạng Thái':<15}")
    print("-"*70)
    
    for admin in admins:
        status = "✅ Hoạt động" if admin['is_active'] else "❌ Vô hiệu"
        print(f"{admin['id']:<5} {admin['username']:<20} {admin['email']:<25} {status:<15}")
    
    print("="*70)


def change_password_menu(manager):
    """Menu đổi mật khẩu"""
    print("\n" + "="*70)
    print("🔑 ĐỔI MẬT KHẨU ADMIN".center(70))
    print("="*70)
    
    # Hiện danh sách admin
    admins, _ = manager.list_admins()
    if not admins:
        print("\n❌ Chưa có admin nào!")
        return
    
    print("\n📋 Danh sách admin:")
    for admin in admins:
        print(f"   {admin['id']} - {admin['username']} ({admin['email']})")
    
    try:
        user_id = int(input("\n👤 Nhập ID admin: ").strip())
    except ValueError:
        print("❌ ID không hợp lệ!")
        return
    
    new_password = input("🔑 Mật khẩu mới: ").strip()
    
    if not new_password or len(new_password) < 6:
        print("❌ Password phải ít nhất 6 ký tự!")
        return
    
    success, message = manager.change_password(user_id, new_password)
    
    print("\n" + "="*70)
    print(message)
    print("="*70)


def toggle_status_menu(manager):
    """Menu bật/tắt trạng thái"""
    print("\n" + "="*70)
    print("✓ BẬT/TẮT TRẠNG THÁI ADMIN".center(70))
    print("="*70)
    
    # Hiện danh sách admin
    admins, _ = manager.list_admins()
    if not admins:
        print("\n❌ Chưa có admin nào!")
        return
    
    print("\n📋 Danh sách admin:")
    for admin in admins:
        status = "✅ Hoạt động" if admin['is_active'] else "❌ Vô hiệu"
        print(f"   {admin['id']} - {admin['username']} ({status})")
    
    try:
        user_id = int(input("\n👤 Nhập ID admin: ").strip())
    except ValueError:
        print("❌ ID không hợp lệ!")
        return
    
    success, message = manager.toggle_admin_status(user_id)
    
    print("\n" + "="*70)
    print(message)
    print("="*70)


def delete_admin_menu(manager):
    """Menu xóa admin"""
    print("\n" + "="*70)
    print("🗑️  XÓA ADMIN".center(70))
    print("="*70)
    
    # Hiện danh sách admin
    admins, _ = manager.list_admins()
    if not admins:
        print("\n❌ Chưa có admin nào!")
        return
    
    print("\n📋 Danh sách admin:")
    for admin in admins:
        print(f"   {admin['id']} - {admin['username']} ({admin['email']})")
    
    try:
        user_id = int(input("\n👤 Nhập ID admin cần xóa: ").strip())
    except ValueError:
        print("❌ ID không hợp lệ!")
        return
    
    confirm = input("⚠️  Xác nhận xóa? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Đã hủy!")
        return
    
    success, message = manager.delete_admin(user_id)
    
    print("\n" + "="*70)
    print(message)
    print("="*70)


def main():
    """Hàm chính"""
    print_banner()
    
    manager = AdminManager()
    
    while True:
        print_menu()
        
        choice = input("👉 Nhập lựa chọn (1-6): ").strip()
        
        if choice == '1':
            create_admin_menu(manager)
        elif choice == '2':
            list_admins_menu(manager)
        elif choice == '3':
            change_password_menu(manager)
        elif choice == '4':
            toggle_status_menu(manager)
        elif choice == '5':
            delete_admin_menu(manager)
        elif choice == '6':
            print("\n👋 Cảm ơn bạn! Tạm biệt!\n")
            sys.exit(0)
        else:
            print("\n❌ Lựa chọn không hợp lệ. Vui lòng chọn lại!\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏸️  Đã dừng.\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Lỗi: {e}\n")
        sys.exit(1)
