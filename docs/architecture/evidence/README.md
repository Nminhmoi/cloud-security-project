# Ảnh bằng chứng cho báo cáo

Đã chèn sáu ảnh Ubuntu do nhóm cung cấp ngày 17-09-2026:

- Chương 4, Docker hóa: `docker-compose-ubuntu.png`, `cloudbox-ui-ubuntu.png`.
- Chương 5, môi trường kiểm thử: `smoke-test-ubuntu.png`.
- Chương 5, mô phỏng tấn công: `attack-simulation-results.png` (test tự động).
- Chương 5, tổng hợp kết quả: `unittest-app-details-ubuntu.png`, `unittest-88-pass.png`.

Ảnh gốc giữ trong `../evidence-archive-ubuntu/`. Tên `docker-compose-ubutu.png`
được chuẩn hóa thành `docker-compose-ubuntu.png` ở bản sao dùng để chèn.
Hai suite có 78/78 và 10/10 test đạt; log cho thấy Python 3.14 trên máy ảo.
Ảnh AWS vẫn chưa có trong bộ ảnh này.

Đặt ảnh PNG vào thư mục này với đúng tên dưới đây, sau đó biên dịch lại
`ATTT1.tex`. Các khung giữ chỗ trong báo cáo sẽ tự động được thay bằng ảnh.

- `docker-compose-ubuntu.png`: phiên bản Ubuntu/Docker, `docker compose ps` và HTTP health check trên máy ảo.
- `cloudbox-ui-ubuntu.png`: giao diện CloudBox truy cập qua IP máy ảo Ubuntu.
- `terraform-apply-success.png`: phần kết quả `terraform apply` đã che dữ liệu nhạy cảm.
- `aws-resource-status.png`: ALB/target, EC2/SSM, RDS, S3, IAM và CloudWatch.
- `cloudbox-alb-access.png`: CloudBox hoạt động qua URL của ALB.
- `aws-integration-smoke-test.png`: kết quả hai script kiểm tra sau triển khai.
- `unittest-88-pass.png`: kết quả chạy lại hai bộ test trên máy ảo Ubuntu.
- `attack-simulation-results.png`: yêu cầu/phản hồi của các kịch bản thực sự đã chạy trên Ubuntu.

Các ảnh tạo trên Windows/Docker Desktop đã được chuyển sang thư mục
`../evidence-archive-windows/` và không được chèn trong báo cáo.

Che số tài khoản AWS, ARN đầy đủ, endpoint nhạy cảm, cookie, CSRF token, OTP,
secret và nội dung tài liệu riêng trước khi chèn. Không đưa Terraform state hoặc
toàn bộ plan vào báo cáo.
