# CI/CD và các cổng kiểm tra bảo mật

CloudBox sử dụng hai workflow GitHub Actions:

- `.github/workflows/ci.yml` chạy khi có pull request hoặc push lên `main`.
- `.github/workflows/deploy.yml` chỉ chạy khi người dùng chủ động chọn manual dispatch.

Mọi action bên thứ ba đều được ghim bằng commit SHA đầy đủ. Dependabot kiểm tra
các SHA này cùng dependency Python, Docker và Terraform mỗi tuần.

## Tích hợp liên tục

Workflow CI có bốn job chính:

1. `Python tests` compile source và chạy unit test của ứng dụng cùng module
   security trên Python 3.12, trùng với Docker image.
2. `Python security` chạy `pip-audit` cho runtime dependency và Bandit cho mã
   ứng dụng. Finding Bandit mức High sẽ làm job thất bại.
3. `Terraform` kiểm tra format và validate root module mà không kết nối remote
   backend hoặc AWS account.
4. `Container and IaC security` dùng Trivy để tìm secret đã commit, lỗi cấu hình
   hạ tầng và lỗ hổng High/Critical đã có bản sửa trong application image.

Runtime image ghim digest của Python base image, cài Debian security update khi
build và gỡ công cụ đóng gói Python sau khi cài dependency. Dependabot đề xuất
cập nhật digest để mỗi thay đổi đều rõ ràng và có thể xem xét.

Ngoại lệ Trivy nằm trong `.trivyignore.yaml`. Mỗi ngoại lệ giới hạn ở một file
và có lý do. Các ngoại lệ hiện tại mô tả lựa chọn có chủ ý cho môi trường dev:
ALB công khai, HTTP còn tồn tại khi chưa có domain/ACM, bootstrap chỉ dùng
outbound TCP 80/443 và S3 dùng SSE-S3 không phát sinh thêm phí. Phải xem lại các
ngoại lệ trước khi mở môi trường công khai.

Nên cấu hình branch protection của `main` yêu cầu cả bốn job đạt trước khi
merge. CI chỉ có quyền `contents: read`, không có AWS token permission hoặc
deployment secret.

Chạy các cổng kiểm tra Python ở local:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m unittest discover -s security -p "test_*.py" -v
.venv\Scripts\python.exe -m pip_audit -r app\requirements.txt --strict --progress-spinner off
.venv\Scripts\python.exe -m bandit -r app scripts security `
  -x security/iam/test_iam.py,security/monitoring/test_monitoring.py `
  --severity-level high
trivy fs --scanners secret,misconfig --severity HIGH,CRITICAL `
  --ignorefile .trivyignore.yaml --skip-dirs .venv .
```

## Triển khai AWS có kiểm soát

Workflow triển khai dùng GitHub OIDC để lấy AWS credentials ngắn hạn. Không
thêm `AWS_ACCESS_KEY_ID` hoặc `AWS_SECRET_ACCESS_KEY` vào repository secrets.

Tạo GitHub environment tên `cloudbox-dev` và cấu hình:

| Loại | Tên | Ví dụ hoặc mục đích |
|---|---|---|
| Variable | `AWS_REGION` | `ap-southeast-1` |
| Variable | `AWS_ACCOUNT_ID` | AWS account ID gồm 12 chữ số |
| Variable | `AWS_ROLE_ARN` | ARN của OIDC deployment role |
| Variable | `TF_STATE_BUCKET` | Terraform state bucket private đã tồn tại |
| Variable | `TF_STATE_KEY` | `cloudbox/dev/terraform.tfstate` |
| Secret | `TF_VARS_JSON` | JSON tùy chọn chứa Terraform variable không dùng mặc định |

Không đặt `app_git_ref` trong `TF_VARS_JSON`; workflow luôn ghim biến này vào
Git commit được chọn. Ví dụ cấu hình development:

```json
{
  "environment": "dev",
  "instance_type": "t3.micro",
  "db_instance_class": "db.t3.micro",
  "deletion_protection": false
}
```

Yêu cầu reviewer cho environment `cloudbox-dev` và giới hạn deployment branch
ở `main`. Workflow cũng từ chối `apply=true` bên ngoài `refs/heads/main`.

## Quan hệ tin cậy AWS OIDC

Tạo GitHub OIDC provider cho `https://token.actions.githubusercontent.com` với
audience `sts.amazonaws.com`, sau đó cấu hình trust policy của deployment role
chỉ cho repository và protected environment này:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:OWNER/REPOSITORY:environment:cloudbox-dev"
        }
      }
    }
  ]
}
```

Gắn deployment policy chỉ gồm các service và resource do Terraform module quản
lý. Tránh `AdministratorAccess`; deployment role phải tách biệt với EC2
application role có phạm vi nhỏ hơn nhiều.

## Chạy CD

Mở **Actions → Deploy CloudBox to AWS → Run workflow**:

- Không bật `apply` nếu chỉ muốn tạo Terraform plan.
- Chỉ bật `apply` sau khi đã xem plan và chi phí dự kiến.

Sau khi apply, workflow chờ ALB target, chạy AWS integration test chỉ đọc rồi
chạy smoke test cho endpoint công khai. Terraform plan không được lưu thành
artifact vì file plan có thể chứa giá trị được suy ra từ secret.
