# Công cụ kiểm tra bảo mật

Thư mục này chứa công cụ kiểm tra bảo mật và các chính sách mẫu của dự án. Các file JSON trong `policies/` dùng để thử công cụ kiểm tra, không tự động áp dụng lên AWS. Cấu hình dùng để triển khai hạ tầng nằm trong `terraform/`.

Chạy toàn bộ test của module security từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s security -t . -v
```

Kiểm tra tất cả IAM policy mẫu:

```powershell
.\.venv\Scripts\python.exe -m security.iam.iam_validator
```

Kiểm tra cơ sở dữ liệu SQLite trên máy cá nhân mà không thay đổi dữ liệu:

```powershell
.\.venv\Scripts\python.exe -m security.iam.user_evaluator --db database.db
.\.venv\Scripts\python.exe -m security.monitoring.security_monitoring --db database.db
```

Với RDS, đặt `DATABASE_URL` hoặc truyền `--database-url`. Không ghi thông tin
đăng nhập trực tiếp vào lịch sử shell và không commit chúng vào repository.

Công cụ giám sát bảo mật chỉ kiểm tra trạng thái cơ sở dữ liệu tại thời điểm chạy. Công cụ trả
về `INCOMPLETE` khi chưa có dữ liệu theo dõi các lần đăng nhập thất bại. File JSON mô tả alarm
đăng nhập thất bại cũng chỉ là cấu hình mẫu cho đến khi ứng dụng gửi số liệu
và Terraform tạo CloudWatch alarm tương ứng.

IAM validator áp dụng các quy tắc cục bộ của dự án. Kết quả hợp lệ không chứng
minh một policy an toàn tuyệt đối và không thay thế AWS IAM Access Analyzer.
