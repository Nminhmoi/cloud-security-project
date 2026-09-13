# Kiến trúc hệ thống

## Phạm vi

CloudBox là ứng dụng quản lý và chia sẻ tài liệu dùng Flask. Dự án ưu tiên khả
năng chạy miễn phí ở local, đồng thời cung cấp Terraform để chứng minh phương án
triển khai AWS. Các dịch vụ phát sinh chi phí được để tùy chọn.

## Kiến trúc logic

```text
Browser / REST client
        |
        v
Flask routes + CSRF + rate limiting
        |
        +--> Authentication / OTP / session
        +--> RBAC + owner/share authorization
        +--> Document service
                 |
                 +--> SQLite hoặc RDS MySQL: metadata
                 +--> Local filesystem hoặc S3: nội dung file
```

Route xử lý HTTP và kiểm tra quyền ở biên. Service chứa nghiệp vụ dùng chung;
model SQLAlchemy quản lý dữ liệu; storage service chọn local filesystem hoặc S3
theo cấu hình `AWS_S3_BUCKET`.

## Môi trường cục bộ

```text
localhost:5000 -> Flask -> SQLite + app/uploads
```

Đây là đường chạy nhanh, không yêu cầu tài khoản AWS. Docker Compose cung cấp
biến thể Gunicorn + MySQL để kiểm tra migration và dữ liệu dùng chung giữa nhiều
container.

## Phương án AWS

```text
Internet
   |
   v
Application Load Balancer
   |
   v
EC2 + Docker + Gunicorn
   |          |          |
   v          v          v
RDS MySQL    S3          SES
   |
CloudWatch Logs / alarms + VPC Flow Logs
```

- ALB là điểm vào công khai; EC2 port 5000 chỉ nhận traffic từ security group
  của ALB.
- EC2 nằm trong public subnet để tránh chi phí NAT Gateway nhưng không mở SSH;
  quản trị dùng Systems Manager Session Manager.
- RDS nằm trong hai private database subnet, không public và chỉ nhận MySQL từ
  security group của EC2.
- S3 giữ nội dung file; RDS giữ metadata và quan hệ chia sẻ.
- EC2 dùng instance profile và temporary credentials, không dùng access key
  tĩnh.
- HTTPS, SES, AWS Backup và restore testing có thể bật riêng tùy điều kiện demo
  và chi phí.

## Luồng tải lên và tải xuống

Upload đi qua xác thực, permission, giới hạn request, kiểm tra tên/MIME/chữ ký,
kiểm tra archive, quota và SHA-256 trước khi lưu. Database chỉ được commit sau
khi object đã lưu; nếu commit thất bại, service cố gắng xóa object mồ côi.

Download luôn truy vấn tài liệu với điều kiện chủ sở hữu hoặc quan hệ chia sẻ.
`storage_key` riêng tư không được trả về API. Trạng thái `pending`, `infected`
và `failed` bị chặn; `not_scanned` vẫn được phép tải vì dự án chưa bật malware
scanner trả phí.

## Quyết định phù hợp quy mô bài tập

- Một EC2 thay vì Auto Scaling Group.
- RDS Single-AZ mặc định; Multi-AZ là tùy chọn.
- HTTP được phép cho môi trường dev; HTTPS cần domain và ACM.
- SSE-S3 thay vì KMS customer-managed key.
- Rate-limit memory storage cho local; Redis chỉ cần khi mở rộng nhiều instance.
- Không bật WAF hoặc malware scanning mặc định.

Đây là giới hạn phạm vi có chủ ý, không phải tuyên bố kiến trúc production.
