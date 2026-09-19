# Cài đặt và chạy dự án

## Yêu cầu

- Python 3.12
- Git
- Các package trong `app/requirements.txt`
- Docker Desktop nếu muốn chạy với MySQL

## Cài đặt

```powershell
cd <duong-dan-toi-project>\cloud-security-project
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r app\requirements.txt
```

## Chạy ứng dụng

```powershell
.venv\Scripts\python.exe app\app.py
```

Sau khi chạy lệnh, mở `http://localhost:5000` trong trình duyệt để sử dụng ứng dụng.

Không dùng `python -c "from app.app import app"` trong cấu trúc hiện tại vì các module đang dùng import tuyệt đối từ thư mục `app`.

## Cơ sở dữ liệu

Đường dẫn mặc định là `cloud-security-project/database.db`. Có thể đổi bằng biến môi trường:

```powershell
$env:DATABASE_PATH = "D:\data\cloudbox.db"
.venv\Scripts\python.exe app\app.py
```

Nếu file chưa tồn tại, SQLite tự tạo file và `init_db()` tạo bảng. Với môi
trường Docker/MySQL, schema được quản lý bằng Alembic. Luôn sao lưu trước khi
nâng cấp.

Tạo và kiểm tra một bản sao lưu SQLite:

```powershell
.venv\Scripts\python.exe scripts\database_backup.py backup
.venv\Scripts\python.exe scripts\database_backup.py verify backups\cloudbox-TIMESTAMP.db
```

`database.db` là dữ liệu runtime, bị loại khỏi Git và không thể khôi phục bằng
`git restore`.

## Chạy bằng Docker và MySQL

Sao chép `.env.example` thành `.env`, đặt ít nhất `DB_PASSWORD`,
`MYSQL_ROOT_PASSWORD` và `SECRET_KEY`, sau đó chạy:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml up --build
```

Xem [DOCKER_MYSQL.md](DOCKER_MYSQL.md) và
[DATABASE_MIGRATIONS.md](DATABASE_MIGRATIONS.md) để kiểm tra khả năng giữ dữ liệu sau khi khởi động lại và cách chạy migration.

## Tài khoản admin

Tạo admin đầu tiên hoặc quản lý admin hiện có:

```powershell
.venv\Scripts\python.exe admin.py
```

Chạy script này từ thư mục gốc khi cần tạo hoặc quản lý tài khoản quản trị.

## Kiểm tra

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
sqlite3 database.db "PRAGMA integrity_check;"
```

Kết quả integrity mong đợi là `ok`.

## Cấu hình an toàn cho môi trường cục bộ

- Không commit `.env`, database, file tải lên, Terraform state hoặc plan.
- `OTP_DELIVERY_MODE=local` chỉ dùng khi demo; OTP sẽ xuất hiện trong terminal.
- `SESSION_COOKIE_SECURE=false` phù hợp với HTTP localhost. Khi dùng HTTPS phải
  chuyển thành `true`.
- Không dùng Flask development server làm bằng chứng cho deployment; Docker sử
  dụng Gunicorn.
