# Bằng chứng sử dụng trong báo cáo

Thư mục này lưu tập trung các ảnh và dữ liệu kiểm thử được tham chiếu trong `ATTT1.tex`.

Ảnh nguồn cũ được giữ trong `originals/ubuntu/` để đối chiếu; báo cáo không tham chiếu trực tiếp các tệp này. Kết quả do script tạo về sau nằm trong `generated/windows/`.

## Triển khai và kiểm thử AWS

- `terraform-validation-state.png`: Terraform validate và danh sách tài nguyên trong state.
- `terraform-apply-success.png`: kết quả Terraform apply/refresh thành công.
- `aws-resource-status.png`: kết quả kiểm tra tích hợp AWS đạt 9/9.
- `aws-ec2-runtime.png`: container EC2 healthy và endpoint cục bộ trả HTTP 200.
- `aws-integration-unit-tests-10.png`: 10 unit test của mô-đun kiểm tra AWS đều đạt.
- `cloudbox-alb-access.png`: ứng dụng hoạt động qua URL của Application Load Balancer.

## Docker và kiểm thử ứng dụng

- `docker-compose-ubuntu.png`, `cloudbox-ui-ubuntu.png`: triển khai Docker trên Ubuntu.
- `smoke-test-ubuntu.png`: kiểm thử nhanh ứng dụng.
- `unittest-app-details-ubuntu.png`, `unittest-88-pass.png`: kết quả bộ unit test ứng dụng.
- `attack-simulation-results.png`: kết quả mô phỏng tấn công.
- `restart-sha256-ubuntu.png`: container hoạt động sau khởi động lại và đối chiếu SHA-256.

## Phân quyền và chia sẻ tài liệu

- `admin-access-allowed.png`: tài khoản quản trị truy cập trang quản trị, HTTP 200.
- `normal-user-admin-denied.png`: người dùng thường bị từ chối, HTTP 403.
- `rbac-access-results.json`: URL, trình tự thao tác và mã HTTP của phép thử RBAC.
- `document-share-granted.png`, `document-share-recipient.png`: cấp quyền và tải tài liệu được chia sẻ.
- `document-unshared-denied.png`, `document-share-revoked.png`: từ chối và thu hồi quyền chia sẻ.

## CI và quét bảo mật

- `github-actions-success.png`: quy trình GitHub Actions thành công.
- `pip-audit-ci.png`, `bandit-ci.png`: kiểm tra dependency và mã nguồn Python.
- `trivy-iac.png`, `trivy-image.png`: quét Terraform và Docker image.

Khi bổ sung ảnh, cần che thông tin nhạy cảm như khóa truy cập, token, cookie, OTP và bí mật. Không đưa Terraform state hoặc toàn bộ plan có dữ liệu nhạy cảm vào báo cáo.
