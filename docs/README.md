# Tài liệu CloudBox

Thư mục này là điểm bắt đầu cho tài liệu chi tiết của dự án. `README.md` ở thư
mục gốc chỉ giới thiệu và hướng dẫn chạy nhanh; thông tin chuyên sâu được đặt ở
đây để tránh làm trang chính quá dài.

## Tổng quan

- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md): mục tiêu, phạm vi và giới hạn của bài tập lớn.
- [ARCHITECTURE.md](ARCHITECTURE.md): kiến trúc ứng dụng, dữ liệu và AWS.
- [SECURITY.md](SECURITY.md): threat model, security controls và các giới hạn đã biết.

## Phát triển và sử dụng

- [SETUP.md](SETUP.md): cài đặt và chạy bằng SQLite hoặc Docker/MySQL.
- [API.md](API.md): REST API, session và CSRF.
- [RBAC.md](RBAC.md): role, permission, object-level authorization và admin UI.
- [DATABASE_MIGRATIONS.md](DATABASE_MIGRATIONS.md): model và Alembic migration.
- [DOCKER_MYSQL.md](DOCKER_MYSQL.md): kiểm thử nhiều container dùng chung MySQL.
- [FILE_UPLOAD_SECURITY.md](FILE_UPLOAD_SECURITY.md): upload validation, quota và vòng đời file.

## AWS và vận hành

- [../terraform/README.md](../terraform/README.md): Terraform và quy trình triển khai.
- [CI_CD.md](CI_CD.md): CI security gates và deploy thủ công qua OIDC.
- [AWS_INTEGRATION_TESTING.md](AWS_INTEGRATION_TESTING.md): kiểm tra control plane sau deploy.
- [HTTPS_DEPLOYMENT.md](HTTPS_DEPLOYMENT.md): ACM, Route 53 và HTTPS.
- [SES_OTP.md](SES_OTP.md): gửi OTP bằng Amazon SES.
- [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md): backup và khôi phục SQLite/RDS.

## Quy tắc duy trì tài liệu

- Model trong `app/models/` và migration trong `migrations/` là nguồn sự thật
  của schema; không duy trì một bản SQL schema thủ công song song.
- Terraform là nguồn sự thật cho tài nguyên AWS; JSON trong `security/policies/`
  chỉ là ví dụ dùng cho local linter.
- Chỉ mô tả một control là “đã triển khai” khi có code hoặc test chứng minh.
- Khi đổi route, biến môi trường hay Terraform output, cập nhật tài liệu liên
  quan trong cùng pull request.

