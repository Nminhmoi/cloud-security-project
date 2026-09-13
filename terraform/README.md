# Hạ tầng AWS của CloudBox

Root module này tạo VPC trên hai Availability Zone, ALB public, một EC2 chạy
ứng dụng và được quản trị qua SSM, RDS MySQL private, S3 private có versioning,
Secrets Manager, VPC Flow Logs và CloudWatch alarms. Port 5000 của EC2 chỉ nhận
kết nối từ ALB; database không bao giờ được public.

Cấu hình được chia theo chức năng (`data.tf`, `locals.tf`, `network.tf`,
`security-groups.tf`, `database.tf`, `storage.tf`, `iam.tf`,
`load-balancer.tf`, `compute.tf`, `observability.tf`) nhưng vẫn là một root
module. Di chuyển resource block giữa các file này không đổi Terraform address.
Logic bootstrap EC2 nằm trong `templates/cloud-init.sh.tftpl` để có thể review
và kiểm thử riêng.

## 1. Tạo bucket lưu trạng thái từ xa một lần

Backend bucket phải tồn tại trước `terraform init`. Chọn tên bucket duy nhất
toàn cầu và tạo nó bên ngoài root module này:

```bash
export TF_STATE_BUCKET="your-account-cloudbox-terraform-state"
export AWS_REGION="ap-southeast-1"

aws s3api create-bucket \
  --bucket "$TF_STATE_BUCKET" \
  --region "$AWS_REGION" \
  --create-bucket-configuration LocationConstraint="$AWS_REGION"
aws s3api put-public-access-block \
  --bucket "$TF_STATE_BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-versioning \
  --bucket "$TF_STATE_BUCKET" \
  --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption \
  --bucket "$TF_STATE_BUCKET" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

Với Region `us-east-1`, bỏ `--create-bucket-configuration`.

## 2. Khởi tạo và kiểm tra

Chạy từ thư mục `terraform`. Native S3 lockfile bảo vệ state khi có thao tác
đồng thời nên không cần DynamoDB table.

```bash
terraform init -migrate-state \
  -backend-config="bucket=$TF_STATE_BUCKET" \
  -backend-config="key=cloudbox/dev/terraform.tfstate" \
  -backend-config="region=$AWS_REGION"
terraform fmt -check
terraform validate
```

Commit `.terraform.lock.hcl`; không commit `.terraform/`, state, plan hoặc file
`.tfvars` chứa secret.

## 3. Tạo kế hoạch với phiên bản ứng dụng cố định

Triển khai chính xác một commit thay vì branch có thể thay đổi:

```bash
export APP_GIT_REF="$(git -C .. rev-parse HEAD)"
terraform plan -var="app_git_ref=$APP_GIT_REF" -out=tfplan
terraform apply tfplan
```

Commit được tham chiếu phải tồn tại trên GitHub vì EC2 checkout nó trong
cloud-init. Deployment cũ sử dụng state address migration trong `moved.tf`,
nhưng EC2 và S3 bucket ban đầu vẫn có thể cần thay thế do immutable setting thay
đổi. Xem kỹ plan và sao chép object hiện có trước khi chấp nhận thay bucket.

Nếu dùng HTTPS với certificate có sẵn trong cùng Region, thêm:

```bash
-var="domain_name=cloudbox.example.com" \
-var="certificate_arn=arn:aws:acm:REGION:ACCOUNT:certificate/ID"
```

Khi không có certificate hoặc cấu hình managed domain, ALB dùng HTTP cho dev và
output `https_enabled` là false. Không coi chế độ này là phù hợp để mở công khai.

Terraform cũng có thể yêu cầu certificate, xác minh DNS, tạo Route 53 alias và
trả về custom HTTPS URL:

```bash
-var="domain_name=cloudbox.example.com" \
-var="route53_zone_id=Z1234567890"
```

Hosted zone phải public và domain thuộc quyền kiểm soát của bạn. Xem
[HTTPS_DEPLOYMENT.md](../docs/HTTPS_DEPLOYMENT.md) để biết điều kiện và cách
smoke test sau deployment.

Nếu cần môi trường có khả năng bảo vệ cao hơn, có thể bật:

```bash
-var="db_multi_az=true" \
-var="deletion_protection=true" \
-var="alarm_email=operator@example.com"
```

Phải xác nhận SNS email subscription trước khi alarm có thể gửi thông báo.

Upload mặc định tối đa 16 MiB mỗi file, quota 500 MiB mỗi user và giữ thùng rác
30 ngày. Có thể đổi từng giá trị:

```bash
-var="max_upload_bytes=16777216" \
-var="user_storage_quota_bytes=524288000" \
-var="deleted_document_retention_days=30"
```

Cloud-init bật systemd timer hằng ngày để xóa vĩnh viễn document record và
object local/S3 hết hạn trong thùng rác. S3 Versioning giữ version object đã xóa
theo lifecycle recovery window.

Password-reset OTP dùng Amazon SES khi có sender đã xác minh:

```bash
-var="ses_sender_email=owner@example.com"
```

Terraform tạo email identity nhưng người dùng vẫn phải xác nhận email AWS gửi.
SES sandbox chỉ gửi được tới recipient đã xác minh. Nếu không truyền biến này,
OTP trên AWS bị tắt và không được ghi vào application log.

Point-in-time recovery của RDS mặc định giữ bảy ngày. AWS Backup và restore
testing là tùy chọn vì tạo thêm chi phí lưu trữ hoặc resource tạm:

```bash
-var="db_backup_retention_days=14" \
-var="enable_aws_backup=true" \
-var="aws_backup_retention_days=35" \
-var="enable_restore_testing=true"
```

Xem [BACKUP_AND_RECOVERY.md](../docs/BACKUP_AND_RECOVERY.md) và
[SES_OTP.md](../docs/SES_OTP.md) để biết cách xác minh và khôi phục.

## 4. Vận hành

Dùng `terraform output application_url` để lấy entry point công khai. Kết nối
EC2 bằng AWS Systems Manager Session Manager; SSH không được mở. Log bootstrap
nằm ở `/var/log/cloud-init-output.log`; log application container được gửi tới
CloudWatch log group trong Terraform output.

Từ thư mục gốc, kiểm tra AWS control plane mà không thay đổi resource, sau đó
kiểm tra endpoint đã triển khai:

```powershell
.venv\Scripts\python.exe scripts\aws_integration_test.py --region ap-southeast-1
$applicationUrl = terraform -chdir=terraform output -raw application_url
.venv\Scripts\python.exe scripts\smoke_test_deployment.py $applicationUrl --allow-http
```

Bỏ `--allow-http` khi HTTPS đã bật. Xem
[AWS_INTEGRATION_TESTING.md](../docs/AWS_INTEGRATION_TESTING.md) để biết toàn bộ
quy trình nghiệm thu.
