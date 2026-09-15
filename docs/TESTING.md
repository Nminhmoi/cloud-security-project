# Quy trình kiểm thử và ghi nhận kết quả

## 1. Mục tiêu

Quy trình kiểm thử xác minh ba nhóm yêu cầu của CloudBox:

1. Chức năng chính hoạt động đúng: tài khoản, tài liệu, chia sẻ và quản trị.
2. Các biện pháp bảo mật được thực thi ở phía server, không chỉ xuất hiện trên
   giao diện hoặc tài liệu.
3. Cấu hình triển khai Docker, CI và Terraform có thể được kiểm tra lặp lại.

Quy trình ưu tiên test tự động không phát sinh chi phí. Test Docker/MySQL và AWS
được tách riêng vì cần hạ tầng hoặc tài khoản bên ngoài.

## 2. Môi trường kiểm thử

| Thành phần | Môi trường local | Môi trường CI chuẩn |
|---|---|---|
| Hệ điều hành | Windows/PowerShell | Ubuntu 24.04 |
| Python | Môi trường ảo `.venv` | Python 3.12 |
| Database | SQLite tạm cho từng test | SQLite tạm cho từng test |
| AWS | Mock hoặc dữ liệu Terraform output mẫu | Không cấp AWS credentials |
| Framework test | `unittest` | `unittest` |

Mỗi test tạo dữ liệu riêng và không phụ thuộc `database.db` đang dùng để demo.
Các lời gọi S3 và SES trong unit test được mock nên không gửi email, không tải
file và không phát sinh chi phí AWS.

## 3. Ma trận kiểm thử

| Lớp kiểm thử | Mục đích | Công cụ hoặc file chính |
|---|---|---|
| Unit/API | Xác minh request, validation và trạng thái trả về | `tests/test_api.py` |
| Xác thực | Login, lockout, OTP, CSRF, session | `tests/test_security_controls.py`, `tests/test_email_service.py` |
| Phân quyền | RBAC, admin và object ownership | `tests/test_admin_rbac.py`, `tests/test_api.py` |
| File | S3 mock, path traversal, ZIP bomb, checksum | `tests/test_storage_service.py` |
| Dữ liệu | Cấu hình MySQL, backup và restore SQLite | `tests/test_config.py`, `tests/test_database_backup.py` |
| Security utilities | IAM policy linter và database audit | `security/**/test_*.py` |
| IaC/CI | Terraform, workflow, Docker và scanner configuration | Terraform CLI, `tests/test_ci_configuration.py` |
| Sau triển khai | AWS control plane và HTTP/HTTPS endpoint | `scripts/aws_integration_test.py`, `scripts/smoke_test_deployment.py` |

## 4. Trình tự thực hiện

### Bước 1: Chuẩn bị

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r app\requirements.txt
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Không dùng database hoặc tài khoản AWS thật cho unit test. Nếu cần lưu output
làm phụ lục, không đưa secret, cookie, OTP hoặc Terraform state vào báo cáo.

### Bước 2: Kiểm tra cú pháp và dependency đã cài

```powershell
.venv\Scripts\python.exe -m compileall -q app scripts security tests
.venv\Scripts\python.exe -m pip check
```

Tiêu chí đạt: source compile thành công và không có dependency bị thiếu hoặc
xung đột.

### Bước 3: Chạy test ứng dụng

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Các nhóm hành vi quan trọng phải đạt:

- đăng ký, đăng nhập, đăng xuất và tài khoản bị vô hiệu hóa;
- CSRF, rate limit, account lockout và vô hiệu hóa session cũ;
- owner/shared boundary của tài liệu;
- upload validation, quota, soft delete, restore và purge;
- admin RBAC, thay đổi role/permission và activity log;
- S3/SES error handling thông qua mock.

Trong test mô phỏng SES lỗi, application logger có thể in traceback
`EmailDeliveryError: SES unavailable`. Đây là dữ liệu đầu vào có chủ ý để kiểm
tra fail-closed; chỉ xem là lỗi suite nếu phần tổng kết ghi `FAILED` hoặc process
trả exit code khác `0`.

### Bước 4: Chạy test module security

```powershell
.venv\Scripts\python.exe -m unittest discover -s security -t . -v
```

Tiêu chí đạt: IAM policy mẫu hợp lệ theo quy tắc dự án, policy quá rộng bị từ
chối, audit không sửa database và monitor phân biệt `ALERT`/`INCOMPLETE`.

Test database không tồn tại chủ động in `[ERROR] Security audit failed` để xác
minh công cụ không tự tạo file. Dòng này là kết quả mong đợi nếu toàn suite vẫn
kết thúc bằng `OK`.

### Bước 5: Phân tích bảo mật tĩnh

```powershell
.venv\Scripts\python.exe -m pip_audit -r app\requirements.txt --strict --progress-spinner off
.venv\Scripts\python.exe -m bandit -r app scripts security `
  -x security/iam/test_iam.py,security/monitoring/test_monitoring.py `
  --severity-level high
```

Tiêu chí đạt: `pip-audit` không tìm thấy lỗ hổng vi phạm policy; Bandit không có
finding mức High. Finding thấp hơn phải được xem xét và ghi lý do chấp nhận,
không tự động coi mọi cảnh báo là lỗ hổng có thể khai thác.

Nếu có Trivy ở local:

```powershell
trivy fs --scanners secret,misconfig --severity HIGH,CRITICAL `
  --ignorefile .trivyignore.yaml --skip-dirs .venv .
```

### Bước 6: Kiểm tra Terraform

```powershell
terraform -chdir=terraform fmt -check -recursive
terraform -chdir=terraform init -backend=false -input=false
terraform -chdir=terraform validate
```

Tiêu chí đạt: format đúng và cấu hình hợp lệ mà không cần `apply`. Bước này chỉ
kiểm tra tĩnh, không chứng minh tài nguyên AWS đang tồn tại hoặc hoạt động.

### Bước 7: Kiểm thử Docker/MySQL

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-mysql-containers.ps1 `
  -TemporaryStack -Cleanup
```

Script kiểm tra migration, hai web container dùng chung dữ liệu, restart ứng
dụng và restart MySQL. Tiêu chí đạt là các dòng `PASS` và exit code `0`.

### Bước 8: Kiểm thử AWS sau triển khai

Chỉ chạy bước này khi đã chủ động tạo tài nguyên AWS:

```powershell
.venv\Scripts\python.exe scripts\aws_integration_test.py `
  --region ap-southeast-1

$applicationUrl = terraform -chdir=terraform output -raw application_url
.venv\Scripts\python.exe scripts\smoke_test_deployment.py `
  $applicationUrl --allow-http
```

AWS integration test chỉ đọc control plane. Smoke test kiểm tra endpoint, cookie,
CSRF và security headers. Chỉ bỏ `--allow-http` khi HTTPS thực sự được bật.

Nếu không triển khai vì chi phí, ghi trạng thái **Chưa thực hiện – yêu cầu tài
nguyên AWS**, không ghi `PASS` dựa trên kết quả unit test hoặc `terraform validate`.

## 5. Các ca kiểm thử tiêu biểu để trình bày

| Mã | Ca kiểm thử | Dữ liệu/thao tác | Kết quả mong đợi |
|---|---|---|---|
| AUTH-01 | Login hợp lệ | Đúng username và password | HTTP 200, tạo session |
| AUTH-02 | Brute force | Sai password liên tiếp đến ngưỡng | Khóa tạm thời, HTTP 429 |
| AUTH-03 | Reset password | OTP hợp lệ rồi đặt mật khẩu mới | Session cũ mất hiệu lực |
| CSRF-01 | Thiếu CSRF token | Gửi POST login không có token | HTTP 400 |
| RBAC-01 | User vào trang admin | Session role `user` | HTTP 403 |
| DOC-01 | Đoán ID tài liệu | User khác tải file chưa được chia sẻ | Bị từ chối |
| DOC-02 | Chia sẻ hợp lệ | Owner chia sẻ cho user active | Recipient tải được file |
| FILE-01 | File giả PDF | Tên `.pdf`, signature không đúng | HTTP 400 |
| FILE-02 | ZIP traversal | Archive chứa `../` | Bị từ chối |
| IAM-01 | Policy `Allow Action: *` | Policy mẫu không an toàn | Validator trả INVALID |
| AWS-01 | S3 bucket public | Output/mock cấu hình public | Integration check thất bại |

Trong báo cáo chỉ cần chọn khoảng 8–12 ca đại diện. Toàn bộ danh sách chi tiết
đã được lưu trong source test và có thể đưa vào phụ lục.

## 6. Kết quả xác minh gần nhất

Kết quả chạy local ngày 15/09/2026:

| Hạng mục | Kết quả |
|---|---|
| Test ứng dụng | 78/78 đạt |
| Test module security | 10/10 đạt |
| `pip check` | Đạt, không có dependency bị hỏng |
| Bandit mức High | Đạt, không có finding mức High |
| Terraform format | Đạt |
| Terraform validate | Đạt |
| Docker/MySQL integration | Chưa chạy trong lần xác minh này |
| AWS post-deployment | Chưa chạy trong lần xác minh này |

Số liệu trên là snapshot theo ngày, không nên tự động dùng cho phiên bản source
khác. Khi chốt báo cáo, chạy lại toàn bộ lệnh và lưu commit SHA cùng thời gian.

## 7. Cách ghi kết quả trong báo cáo

Mỗi lần kiểm thử nên lưu:

- commit SHA được kiểm tra;
- ngày giờ và môi trường;
- lệnh hoặc bước thao tác;
- dữ liệu đầu vào không chứa bí mật;
- kết quả mong đợi và kết quả thực tế;
- trạng thái `Đạt`, `Không đạt` hoặc `Chưa thực hiện`;
- ảnh chụp hoặc log tổng kết làm bằng chứng.

Mẫu bảng:

| Mã | Kết quả mong đợi | Kết quả thực tế | Trạng thái | Bằng chứng |
|---|---|---|---|---|
| RBAC-01 | User nhận HTTP 403 khi vào `/admin/users` | HTTP 403 | Đạt | Ảnh/log test |

Không chỉ chụp dòng `OK`; nên kèm một ảnh test suite tổng thể và 2–3 ảnh minh
họa control quan trọng như CSRF, account lockout và object ownership.

