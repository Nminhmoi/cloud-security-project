# Kiểm thử tích hợp AWS

Sau khi triển khai CloudBox lên AWS, dùng hai công cụ sau để kiểm tra cấu hình hạ tầng và khả năng truy cập ứng dụng:

- `scripts/aws_integration_test.py` kiểm tra AWS control plane đã triển khai.
- `scripts/smoke_test_deployment.py` kiểm tra hành vi HTTP/HTTPS công khai.

Kiểm thử AWS chỉ thực hiện thao tác đọc. Công cụ không tải lên object, gửi OTP,
tạo snapshot hay thay đổi tài nguyên AWS. Các nội dung được xác minh gồm:

- AWS account và principal đang hoạt động;
- trạng thái EC2, yêu cầu IMDSv2 token, instance profile và trạng thái SSM;
- RDS không public, có mã hóa, thời gian giữ automated backup và endpoint;
- S3 private, có mã hóa, versioning và nằm đúng Region;
- listener của ALB và EC2 target ở trạng thái healthy;
- IAM profile của EC2, SSM policy và không có câu lệnh `Allow */*` không giới hạn
  trong application policy;
- metadata của RDS secret mà không đọc giá trị secret;
- thời gian giữ log ứng dụng, CloudWatch alarm và VPC Flow Logs đang hoạt động.

## Điều kiện trước khi chạy

Trước khi chạy kiểm thử, cần apply Terraform ít nhất một lần để lưu các output cần thiết vào state. Sau đó đăng nhập AWS CLI bằng tài khoản hoặc vai trò vận hành có quyền đọc:

```powershell
aws sts get-caller-identity
terraform -chdir=terraform output
```

Tài khoản hoặc vai trò vận hành cần quyền đọc STS, EC2, SSM, RDS, cấu hình S3 bucket, ELBv2, IAM,
metadata Secrets Manager, CloudWatch Logs và CloudWatch alarms. Công cụ không
bao giờ gọi `secretsmanager:GetSecretValue`.

## Chạy kiểm thử

Chạy lệnh từ thư mục gốc của dự án:

```powershell
.venv\Scripts\python.exe scripts\aws_integration_test.py `
  --region ap-southeast-1
```

Nếu dùng AWS profile riêng:

```powershell
.venv\Scripts\python.exe scripts\aws_integration_test.py `
  --profile cloudbox-dev `
  --region ap-southeast-1
```

Ngay sau đó, chạy smoke test cho endpoint công khai:

```powershell
$applicationUrl = terraform -chdir=terraform output -raw application_url
.venv\Scripts\python.exe scripts\smoke_test_deployment.py $applicationUrl --allow-http
```

Bỏ `--allow-http` sau khi đã cấu hình HTTPS. Một lần nghiệm thu cho môi trường
công khai phải dùng HTTPS và không được truyền cờ này.

Dùng `--json` để lưu bằng chứng hoặc tích hợp CI. Có thể lưu snapshot output rồi
kiểm tra bằng `--outputs-file`, nhưng Terraform output JSON có thể chứa định danh
hạ tầng nên không được commit:

```powershell
terraform -chdir=terraform output -json | Out-File tf-output.json -Encoding utf8
.venv\Scripts\python.exe scripts\aws_integration_test.py `
  --outputs-file tf-output.json `
  --region ap-southeast-1 `
  --json
Remove-Item -LiteralPath tf-output.json
```

Lệnh trả mã thoát `1` nếu có điều kiện kiểm tra không đạt. Bạn có thể dùng kết quả này trong job triển khai có kiểm soát, với thông tin xác thực AWS ngắn hạn do CI cung cấp.
