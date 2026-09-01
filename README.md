# Cloud Security Project

Ứng dụng Flask quản lý, chia sẻ tài liệu và phân quyền theo vai trò (RBAC), sử dụng SQLite.

## Chạy nhanh trên Windows

```powershell
cd E:\BtapThucHanh\Antoanthongtin\cloud-security-project
.venv\Scripts\python.exe app\app.py
```

Nếu chưa có môi trường ảo:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r app\requirements.txt
.venv\Scripts\python.exe app\app.py
```

Mở `http://localhost:5000`. Database mặc định là `database.db` ở thư mục gốc dự án. SQLite và `init_db()` sẽ tự tạo hoặc nâng cấp schema khi ứng dụng khởi động.

## Quản lý tài khoản admin

```powershell
.venv\Scripts\python.exe admin.py
```

Chọn chức năng tạo admin trong menu khi cần tài khoản đầu tiên. Công cụ `admin.py` nằm ở thư mục gốc và không bắt buộc để web chạy.

## Cấu trúc chính

- `app/app.py`: khởi tạo Flask và đăng ký blueprint.
- `app/database.py`: schema và migration SQLite.
- `app/permissions.py`: kiểm tra role/permission và decorator bảo vệ route.
- `app/routes/admin.py`: API và trang quản trị.
- `app/templates/admin/`: giao diện quản trị.
- `database.db`: dữ liệu runtime, nằm ngoài package `app` theo cấu hình hiện tại.
- `tests/`: kiểm thử phân quyền.

## Tài liệu

- [SETUP_GUIDE.md](SETUP_GUIDE.md): cài đặt, database và xử lý sự cố.
- [RBAC_README.md](RBAC_README.md): mô hình phân quyền hiện tại.
- [PERMISSIONS_GUIDE.md](PERMISSIONS_GUIDE.md): cách dùng các hàm phân quyền.
- [ADMIN_UI_GUIDE.md](ADMIN_UI_GUIDE.md): màn hình và API admin.
- [INTEGRATION_EXAMPLES.md](INTEGRATION_EXAMPLES.md): ví dụ mở rộng, không phải mã đang chạy.
- [DATABASE_SCHEMA.sql](DATABASE_SCHEMA.sql): SQL tham khảo; `app/database.py` mới là nguồn schema chính thức.

## Kiểm thử

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Lưu ý bảo mật

- Đặt `SECRET_KEY` bằng biến môi trường khi triển khai.
- Chỉ các route trong `app/routes/admin.py` đang được bảo vệ bằng `@require_admin`.
- Các request thay đổi dữ liệu dùng `POST`, nhưng dự án **chưa có CSRF token**. Cần bổ sung CSRF protection trước khi triển khai công khai.
- Sao lưu `database.db` trước khi migration hoặc thao tác dữ liệu quan trọng.
