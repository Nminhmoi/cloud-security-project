# Tài liệu CloudBox

Các tài liệu trong thư mục này giải thích cách CloudBox hoạt động, cách cài đặt, kiểm thử và triển khai. Nếu chỉ cần chạy thử ứng dụng, bạn có thể làm theo `README.md` ở thư mục gốc trước.

```text
docs/
├── README.md       # Mục lục tài liệu
├── overview/       # Tổng quan và kiến trúc
├── development/    # Cài đặt, API, cơ sở dữ liệu và Docker
├── security/       # Bảo mật, phân quyền và kiểm tra tệp
├── deployment/     # CI/CD, HTTPS, email và sao lưu
├── testing/        # Quy trình kiểm thử và kiểm tra AWS
└── reports/        # Báo cáo LaTeX, PDF và ảnh
    ├── assets/     # Logo và hình trình bày
    ├── evidence/   # Ảnh, dữ liệu kiểm thử và kết quả tạo tự động
    └── build/      # File tạm biên dịch, không lưu trong Git
```

## Tổng quan

- [PROJECT_OVERVIEW.md](overview/PROJECT_OVERVIEW.md): mục tiêu, phạm vi và giới hạn của bài tập lớn.
- [ARCHITECTURE.md](overview/ARCHITECTURE.md): kiến trúc ứng dụng, dữ liệu và AWS.

## Phát triển và sử dụng

- [SETUP.md](development/SETUP.md): cài đặt và chạy bằng SQLite hoặc Docker/MySQL.
- [API.md](development/API.md): REST API, phiên đăng nhập và CSRF.
- [DATABASE_MIGRATIONS.md](development/DATABASE_MIGRATIONS.md): model và Alembic migration.
- [DOCKER_MYSQL.md](development/DOCKER_MYSQL.md): kiểm thử nhiều container dùng chung MySQL.

## Bảo mật

- [SECURITY.md](security/SECURITY.md): mô hình đe dọa, biện pháp bảo vệ và các giới hạn đã biết.
- [RBAC.md](security/RBAC.md): vai trò, quyền trên tài nguyên và giao diện quản trị.
- [FILE_UPLOAD_SECURITY.md](security/FILE_UPLOAD_SECURITY.md): kiểm tra tệp tải lên, hạn mức lưu trữ và vòng đời tệp.

## AWS và vận hành

- [Hướng dẫn Terraform](../terraform/README.md): cấu hình hạ tầng và quy trình triển khai. Tài liệu này đặt cạnh mã Terraform để tiện cập nhật.
- [CI_CD.md](deployment/CI_CD.md): các bước kiểm tra bảo mật trong CI và triển khai thủ công qua OIDC.
- [HTTPS_DEPLOYMENT.md](deployment/HTTPS_DEPLOYMENT.md): ACM, Route 53 và HTTPS.
- [SES_OTP.md](deployment/SES_OTP.md): gửi OTP bằng Amazon SES.
- [BACKUP_AND_RECOVERY.md](deployment/BACKUP_AND_RECOVERY.md): backup và khôi phục SQLite/RDS.

## Kiểm thử

- [TESTING.md](testing/TESTING.md): quy trình kiểm thử, tiêu chí đạt và cách ghi kết quả.
- [AWS_INTEGRATION_TESTING.md](testing/AWS_INTEGRATION_TESTING.md): kiểm tra cấu hình và hoạt động của AWS sau triển khai.

## Báo cáo

- [Hướng dẫn chỉnh sửa và biên dịch](reports/README.md).
- [Báo cáo PDF](reports/ATTT1.pdf) và [mã nguồn LaTeX](reports/ATTT1.tex).
- [Danh mục ảnh bằng chứng](reports/evidence/README.md).

## Quy tắc duy trì tài liệu

- Đặt tài liệu mới vào nhóm phù hợp; thư mục gốc `docs/` chỉ giữ mục lục này.
- Giữ ảnh và dữ liệu kiểm thử của báo cáo trong `reports/evidence/`; kết quả tạo tự động đặt trong thư mục con `generated/`.
- Model trong `app/models/` và migration trong `migrations/` mô tả cấu trúc cơ sở dữ liệu của dự án. Khi cần thay đổi cấu trúc, hãy cập nhật các file này thay vì giữ thêm một bản SQL viết tay.
- Cấu hình tài nguyên AWS được quản lý bằng Terraform; JSON trong `security/policies/`
  chỉ là ví dụ dùng cho local linter.
- Chỉ mô tả một biện pháp bảo mật là “đã triển khai” khi có code hoặc test chứng minh.
- Khi đổi route, biến môi trường hay Terraform output, cập nhật tài liệu liên
  quan trong cùng pull request.
