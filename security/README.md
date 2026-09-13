# Công cụ kiểm tra bảo mật

Thư mục này chứa các phép kiểm tra và policy mẫu của dự án. Cấu hình AWS được
triển khai thực tế vẫn được định nghĩa trong `terraform/`; các file JSON trong
`policies/` chỉ là ví dụ để xem xét và không tự động được gắn vào tài nguyên AWS.

Chạy toàn bộ test của module security từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s security -t . -v
```

Kiểm tra tất cả IAM policy mẫu:

```powershell
.\.venv\Scripts\python.exe -m security.iam.iam_validator
```

Audit database SQLite local mà không thay đổi dữ liệu:

```powershell
.\.venv\Scripts\python.exe -m security.iam.user_evaluator --db database.db
.\.venv\Scripts\python.exe -m security.monitoring.security_monitoring --db database.db
```

Với RDS, đặt `DATABASE_URL` hoặc truyền `--database-url`. Không ghi thông tin
đăng nhập trực tiếp vào lịch sử shell và không commit chúng vào repository.

Security monitor chỉ audit trạng thái database tại thời điểm chạy. Công cụ trả
về `INCOMPLETE` khi chưa có telemetry đăng nhập thất bại. File JSON mô tả alarm
đăng nhập thất bại cũng chỉ là cấu hình mẫu cho đến khi ứng dụng publish metric
và Terraform tạo CloudWatch alarm tương ứng.

IAM validator áp dụng các quy tắc cục bộ của dự án. Kết quả hợp lệ không chứng
minh một policy an toàn tuyệt đối và không thay thế AWS IAM Access Analyzer.
