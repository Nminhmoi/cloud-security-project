# Triển khai HTTPS

Bạn có thể dùng chứng chỉ ACM có sẵn hoặc để Terraform tạo chứng chỉ và xác minh DNS qua Route 53. HTTP chỉ phù hợp với môi trường phát triển tạm thời; khi mở ứng dụng công khai, cần cấu hình HTTPS.

## Điều kiện

Cần một public domain thuộc quyền kiểm soát của bạn. AWS không cấp public ACM
certificate cho hostname mặc định `*.elb.amazonaws.com` của load balancer. Nếu
muốn Terraform quản lý toàn bộ, public hosted zone của domain phải nằm trong
Route 53 cùng AWS account.

Tìm hosted zone ID:

```powershell
aws route53 list-hosted-zones-by-name --dns-name example.com
```

## Chứng chỉ và DNS do Terraform quản lý

Commit và push ứng dụng trước khi tạo plan:

```powershell
$appGitRef = (git rev-parse HEAD).Trim()
terraform -chdir=terraform plan `
  -var="app_git_ref=$appGitRef" `
  -var="domain_name=cloudbox.example.com" `
  -var="route53_zone_id=Z1234567890" `
  -out=tfplan
```

Terraform yêu cầu ACM certificate, tạo CNAME xác minh, chờ cấp certificate, tạo
ALB alias, bật listener TLS 1.2/1.3 và chuyển port 80 thành redirect HTTPS. ACM
có thể tự gia hạn miễn là DNS validation record vẫn tồn tại.

## Chứng chỉ có sẵn

Nếu certificate và DNS được quản lý ở nơi khác, truyền ARN:

```powershell
terraform -chdir=terraform plan `
  -var="app_git_ref=$appGitRef" `
  -var="domain_name=cloudbox.example.com" `
  -var="certificate_arn=arn:aws:acm:ap-southeast-1:ACCOUNT:certificate/ID"
```

Certificate phải nằm cùng Region với ALB và bao phủ hostname tùy chỉnh. Cấu
hình DNS provider bên ngoài trỏ hostname đó tới ALB.

## Xác minh

Sau khi apply và ALB target trở lại trạng thái healthy:

```powershell
terraform -chdir=terraform output application_url
.venv\Scripts\python.exe scripts\smoke_test_deployment.py `
  https://cloudbox.example.com
```

Smoke test chỉ đọc. Công cụ kiểm tra certificate tin cậy, TLS 1.2/1.3, còn ít
nhất 14 ngày trước khi certificate hết hạn, redirect HTTP sang HTTPS, HSTS/CSP,
các header bảo mật khác, session cookie `Secure`/`HttpOnly`/`SameSite` và CSRF
endpoint.

Kiểm tra yêu cầu HTTP có được chuyển sang HTTPS hay không:

```powershell
curl.exe -I http://cloudbox.example.com
```

Kết quả mong đợi là `HTTP/1.1 301` với `Location` bắt đầu bằng `https://`.
