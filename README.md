# Cloud Security Project

CloudBox là ứng dụng quản lý và chia sẻ tài liệu được xây dựng bằng Flask, có phân quyền theo vai trò (RBAC). Bạn có thể chạy trên máy cá nhân với SQLite hoặc triển khai lên AWS với RDS MySQL và S3.

## Chạy nhanh trên Windows

```powershell
cd <duong-dan-toi-project>\cloud-security-project
.venv\Scripts\python.exe app\app.py
```

Nếu chưa có môi trường ảo:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r app\requirements.txt
.venv\Scripts\python.exe app\app.py
```

Mở `http://localhost:5000`. Cơ sở dữ liệu mặc định là `database.db` ở thư mục gốc dự án. SQLite và `init_db()` sẽ tự tạo hoặc nâng cấp schema khi ứng dụng khởi động.

## Quản lý tài khoản admin

```powershell
.venv\Scripts\python.exe admin.py
```

Để tạo tài khoản quản trị đầu tiên, chọn chức năng tạo admin trong menu. Công cụ `admin.py` nằm ở thư mục gốc; bạn chỉ cần chạy khi muốn quản lý tài khoản quản trị.

## Cấu trúc chính

- `app/app.py`: khởi tạo Flask và đăng ký blueprint.
- `app/database.py`: tương thích và nâng cấp schema SQLite cũ.
- `migrations/`: Alembic migrations dùng cho cả SQLite và RDS.
- `app/permissions.py`: kiểm tra role/permission và decorator bảo vệ route.
- `app/routes/admin.py`: API và trang quản trị.
- `app/templates/admin/`: giao diện quản trị.
- `database.db`: dữ liệu runtime, nằm ngoài package `app` theo cấu hình hiện tại.
- `security/`: local policy linter và công cụ audit database.
- `terraform/`: hạ tầng AWS dưới dạng code.
- `docker/`: image và Compose cho local/MySQL/AWS.
- `tests/`: kiểm thử application, biện pháp bảo mật và cấu hình triển khai.
- `docs/`: tài liệu kiến trúc, bảo mật, phát triển và vận hành.

## Tài liệu

Xem [docs/README.md](docs/README.md) để tra cứu toàn bộ tài liệu. Bạn có thể bắt đầu với các hướng dẫn sau:

- [Tổng quan dự án](docs/overview/PROJECT_OVERVIEW.md)
- [Kiến trúc hệ thống](docs/overview/ARCHITECTURE.md)
- [Tổng quan bảo mật](docs/security/SECURITY.md)
- [Cài đặt](docs/development/SETUP.md)
- [REST API](docs/development/API.md)
- [RBAC và quản trị](docs/security/RBAC.md)
- [Quy trình kiểm thử](docs/testing/TESTING.md)
- [Terraform/AWS](terraform/README.md)
- [Báo cáo và hướng dẫn biên dịch](docs/reports/README.md)

## Kiểm thử

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m unittest discover -s security -t . -v
```

Sau khi triển khai AWS, chạy kiểm thử control plane rồi smoke test endpoint:

```powershell
.venv\Scripts\python.exe scripts\aws_integration_test.py --region ap-southeast-1
$applicationUrl = terraform -chdir=terraform output -raw application_url
.venv\Scripts\python.exe scripts\smoke_test_deployment.py $applicationUrl --allow-http
```

## Lưu ý bảo mật

- Đặt `SECRET_KEY` bằng biến môi trường khi triển khai.
- Các route quản trị được bảo vệ bằng role/permission; tài liệu và chia sẻ kiểm tra quyền sở hữu hoặc quyền truy cập.
- Form và API thay đổi dữ liệu được bảo vệ bằng CSRF token. JavaScript gửi token qua header `X-CSRFToken`.
- Đăng nhập có rate limit, khóa tài khoản tạm thời sau nhiều lần sai và vô hiệu hóa phiên cũ khi đổi mật khẩu.
- Tệp tải lên được giới hạn 16 MiB theo mặc định, kiểm tra phần mở rộng, MIME type và chữ ký tệp.
- Chức năng tải lên có hạn mức lưu trữ theo người dùng, SHA-256, storage key ngẫu nhiên và giới hạn chống ZIP bomb; quyền tài liệu được kiểm tra và áp dụng trên cả web và API.
- Khi chạy nhiều worker/instance, cấu hình `RATELIMIT_STORAGE_URI` bằng Redis thay cho `memory://`.
- AWS deployment dùng SES cho OTP khi cấu hình địa chỉ gửi; nếu thiếu địa chỉ gửi, OTP bị vô hiệu hóa thay vì xuất hiện trong log.
- RDS có point-in-time recovery; AWS Backup và kiểm thử khôi phục có thể bật riêng vì phát sinh chi phí.
- Triển khai công khai cần domain riêng và HTTPS; script smoke test kiểm tra TLS, header bảo mật, cookie và CSRF sau triển khai.
- Sao lưu `database.db` trước khi migration hoặc thao tác dữ liệu quan trọng.
