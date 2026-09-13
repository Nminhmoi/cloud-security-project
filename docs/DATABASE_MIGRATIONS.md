# Mô hình cơ sở dữ liệu và migration

CloudBox dùng SQLAlchemy model và Flask-Migrate/Alembic. SQLite là backend local
mặc định; Docker và phương án AWS dùng cùng model với MySQL trên Amazon RDS.

## Phát triển cục bộ

Khi không có `DATABASE_URL`, ứng dụng mở `database.db` ở thư mục gốc và tự tạo
các bảng còn thiếu để thuận tiện cho local.

Với database SQLite được tạo trước khi dự án dùng Alembic, đánh dấu database ở
revision hiện tại một lần thay vì cố tạo lại các bảng:

```powershell
$env:AUTO_CREATE_SCHEMA = "false"
.venv\Scripts\flask.exe --app app/app.py db stamp head
Remove-Item Env:AUTO_CREATE_SCHEMA
```

Sao lưu `database.db` trước khi stamp hoặc chạy migration mới.

## Cơ sở dữ liệu mới hoặc RDS MySQL

Đặt connection URL và tắt tự động tạo schema:

```text
DATABASE_URL=mysql+pymysql://cloudbox_user:password@host:3306/cloudbox?charset=utf8mb4
AUTO_CREATE_SCHEMA=false
```

Chạy toàn bộ migration đã commit trước khi khởi động web:

```powershell
.venv\Scripts\flask.exe --app app/app.py db upgrade
```

Migration đầu tiên cũng seed role `admin`, `user` và các permission mặc định.
Nó không tạo tài khoản quản trị; dùng `python admin.py` sau migration.

Docker Compose có thể cung cấp riêng `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`
và `DB_PASSWORD`. Ứng dụng tạo và escape PyMySQL URL an toàn;
`DATABASE_URL` được ưu tiên khi cả hai cách cùng tồn tại. Xem
[DOCKER_MYSQL.md](DOCKER_MYSQL.md) để kiểm tra nhiều container dùng chung dữ liệu.

## Phát triển lược đồ

Sau khi thay đổi model:

```powershell
.venv\Scripts\flask.exe --app app/app.py db migrate -m "mo ta thay doi"
.venv\Scripts\flask.exe --app app/app.py db check
.venv\Scripts\flask.exe --app app/app.py db upgrade
```

Luôn xem lại migration được sinh trước khi commit. Môi trường AWS không được
dùng `db.create_all()` thay cho migration có version.
