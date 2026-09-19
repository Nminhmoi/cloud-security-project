# Tổng quan bảo mật

## Mục tiêu và mô hình đe dọa

CloudBox tập trung vào các rủi ro thường gặp khi quản lý tài khoản và chia sẻ tài liệu trên web:

- truy cập tài liệu bằng cách đoán ID;
- người nhận chia sẻ sửa hoặc xóa tài liệu của chủ sở hữu;
- brute-force mật khẩu hoặc OTP;
- CSRF và một số dạng XSS phía trình duyệt;
- tải lên giả phần mở rộng, path traversal và ZIP bomb;
- public bucket, kết nối database công khai hoặc quyền AWS quá rộng;
- lộ secret trong mã nguồn và CI.

## Biện pháp bảo vệ đã triển khai

### Danh tính và phiên đăng nhập

- Mật khẩu được băm bằng Werkzeug; ứng dụng không lưu hoặc ghi mật khẩu dạng rõ vào log.
- Quá trình đăng nhập dùng thông báo lỗi chung, phép băm giả (dummy hash), giới hạn tần suất yêu cầu và khóa tài khoản tạm thời.
- OTP khôi phục mật khẩu được sinh bằng `secrets`, chỉ lưu hash, hết hạn sau hai
  phút và bị thu hồi sau ba lần sai.
- Login gọi `session.clear()`; đổi mật khẩu tăng `session_version`; tài khoản bị
  vô hiệu hóa hoặc xóa mất session ở request tiếp theo.
- Cookie có `HttpOnly`, `SameSite=Lax` và bật `Secure` khi triển khai HTTPS.

### Phân quyền

- Các route quản trị yêu cầu vai trò `admin`; các route tài liệu yêu cầu quyền cụ thể.
- Mọi thao tác trên tài liệu còn kiểm tra chủ sở hữu hoặc `DocumentShare` trong truy
  vấn database.
- Chủ sở hữu mới được sửa, xóa, khôi phục, chia sẻ hoặc thu hồi chia sẻ.
- Có bảo vệ tài khoản admin hiện tại và admin đang hoạt động cuối cùng.

### Yêu cầu và trình duyệt

- Flask-WTF CSRF bảo vệ form và REST API thay đổi dữ liệu.
- CSP dùng nonce cho script; có `nosniff`, `DENY` framing, Referrer Policy,
  Permissions Policy và HSTS khi request là HTTPS.
- Giới hạn kích thước request và rate limit các endpoint nhạy cảm.

### File và dữ liệu

- Allowlist extension/MIME, kiểm tra magic bytes, chuẩn hóa tên file và storage
  key ngẫu nhiên.
- Chống archive traversal, symbolic link và ZIP bomb; có hạn mức lưu trữ và SHA-256.
- SQLite audit mở read-only. S3, EBS và RDS trong phương án AWS đều mã hóa; RDS
  yêu cầu secure transport.

### AWS và pipeline phát hành

- S3 block public access và từ chối HTTP.
- RDS không public; security group chỉ cho phép kết nối từ application host.
- EC2 dùng IAM vai trò least-privilege, IMDSv2 và SSM; không mở SSH.
- Secret lấy từ Secrets Manager; GitHub deployment dùng OIDC credentials ngắn
  hạn.
- CI chạy unit test, pip-audit, Bandit, Terraform validate và Trivy.

## Biện pháp mô phỏng hoặc tùy chọn

| Control | Trạng thái |
|---|---|
| Malware scanning | Chưa bật; chỉ có kiểm tra cấu trúc tệp và `scan_status` |
| HTTPS | Terraform hỗ trợ, cần domain/certificate |
| SES OTP | Tùy chọn; local mode in OTP để demo |
| Failed-login CloudWatch metric | JSON mẫu, ứng dụng chưa publish custom metric |
| AWS Backup/restore testing | Tắt mặc định vì phát sinh chi phí |
| Multi-AZ, WAF, Auto Scaling | Ngoài phạm vi bài tập |

## Giới hạn đã biết

- Rate limit dùng `memory://` không chia sẻ chính xác giữa nhiều worker/instance.
- File `not_scanned` được tải sau kiểm tra cấu trúc tệp; đây không phải antivirus.
- Audit log tập trung vào authentication và thao tác admin, chưa ghi mọi lần
  tải lên, tải xuống hoặc chia sẻ.
- Security monitor là point-in-time database audit, không phải SIEM hoặc
  real-time monitoring.
- IAM JSON trong `security/policies/` là ví dụ, không phải policy Terraform đang
  deploy và không thay thế IAM Access Analyzer.
- Application hiện dùng RDS managed master credential; một deployment chặt hơn
  nên tạo database user chỉ có quyền cần thiết.

## Bằng chứng kiểm thử

- `tests/test_security_controls.py`: CSRF, headers, lockout, rate limit, tải lên
  và session invalidation.
- `tests/test_api.py`: quyền sở hữu tài liệu, sharing, hạn mức lưu trữ và scan status.
- `tests/test_admin_rbac.py`: ranh giới admin, role/permission và audit log.
- `tests/test_storage_service.py`: S3 mock, path traversal và archive safety.
- `security/iam/test_iam.py`, `security/monitoring/test_monitoring.py`: policy
  lint và audit database.
- `scripts/aws_integration_test.py`: kiểm tra read-only tài nguyên AWS sau deploy.

Khi viết báo cáo, chỉ kết luận trong phạm vi đã kiểm thử. Các kết quả trên chưa đủ để khẳng định dự án đã qua pentest, đạt chứng nhận bảo mật hoặc sẵn sàng vận hành thực tế.
