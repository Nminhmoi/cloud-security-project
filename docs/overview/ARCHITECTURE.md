# Kiến trúc hệ thống

## Phạm vi

CloudBox là ứng dụng quản lý và chia sẻ tài liệu dùng Flask. Bạn có thể chạy dự án trên máy cá nhân mà không cần thuê hạ tầng. Dự án cũng có cấu hình Terraform cho phương án triển khai AWS; các dịch vụ bổ sung có tính phí được để ở dạng tùy chọn.

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

Các route tiếp nhận yêu cầu HTTP và kiểm tra quyền truy cập trước khi gọi phần xử lý nghiệp vụ trong service. Model SQLAlchemy quản lý dữ liệu, còn service lưu trữ chọn ổ đĩa cục bộ hoặc S3 dựa trên cấu hình `AWS_S3_BUCKET`.

## Môi trường cục bộ

```text
localhost:5000 -> Flask -> SQLite + app/uploads
```

Cách chạy này không cần tài khoản AWS. Khi muốn kiểm tra migration và việc chia sẻ dữ liệu giữa nhiều container, bạn có thể dùng cấu hình Docker Compose với Gunicorn và MySQL.

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
- RDS nằm trong hai subnet cơ sở dữ liệu riêng tư, không mở công khai và chỉ nhận kết nối MySQL từ
  security group của EC2.
- S3 giữ nội dung file; RDS giữ metadata và quan hệ chia sẻ.
- EC2 dùng instance profile và thông tin xác thực tạm thời, không dùng access key
  tĩnh.
- HTTPS, SES, AWS Backup và kiểm thử khôi phục có thể bật riêng tùy điều kiện demo
  và chi phí.

## Luồng tải lên và tải xuống

Trước khi lưu tệp tải lên, ứng dụng xác thực người dùng, kiểm tra quyền và giới hạn yêu cầu. Tệp cũng được kiểm tra tên, MIME, chữ ký, cấu trúc nén, hạn mức lưu trữ và SHA-256. Thay đổi trong cơ sở dữ liệu chỉ được commit sau
khi object đã lưu; nếu commit thất bại, service sẽ cố gắng xóa tệp vừa lưu để tránh để lại dữ liệu không có bản ghi tương ứng.

Khi tải xuống, ứng dụng chỉ tìm tài liệu thuộc về người dùng hoặc đã được chia sẻ cho họ.
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

Các lựa chọn trên phù hợp với phạm vi bài tập. Để vận hành thực tế, cần đánh giá thêm yêu cầu về tải, tính sẵn sàng và bảo mật.
