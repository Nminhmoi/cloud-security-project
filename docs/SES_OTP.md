# Khôi phục mật khẩu bằng OTP qua Amazon SES

Local có thể dùng `OTP_DELIVERY_MODE=local`. Deployment AWS không ghi giá trị
OTP vào log: chế độ gửi là `ses` khi có `ses_sender_email`; nếu không sẽ là
`disabled` và quá trình reset password dừng an toàn nhưng vẫn giữ cùng luồng
phản hồi trên trình duyệt.

## Tạo và xác minh địa chỉ gửi

Truyền địa chỉ email thuộc quyền kiểm soát của bạn khi tạo Terraform plan:

```powershell
$appGitRef = (git rev-parse HEAD).Trim()
terraform -chdir=terraform plan `
  -var="app_git_ref=$appGitRef" `
  -var="ses_sender_email=owner@example.com" `
  -out=tfplan
```

Apply sẽ tạo SES email identity trong `ap-southeast-1`. Mở email xác minh AWS
gửi tới địa chỉ đó trước khi thử OTP. Kiểm tra trạng thái bằng:

```powershell
aws ses get-identity-verification-attributes `
  --region ap-southeast-1 `
  --identities owner@example.com
```

EC2 instance role chỉ được gửi từ identity do Terraform quản lý. Boto3 sử dụng
temporary credentials của instance profile; không lưu AWS access key trong
`.env` hoặc container.

## SES sandbox

Khi AWS account còn trong SES sandbox, địa chỉ nhận cũng phải được xác minh, trừ
khi dùng mailbox simulator. Nếu phục vụ người dùng thật, cần yêu cầu production
access trong SES console và chỉ bật gửi tại AWS Region dự kiến.

## Kiểm thử nhanh

1. Xác minh sender identity và recipient identity nếu còn trong sandbox.
2. Mở `/forgot-password` qua ALB.
3. Gửi email đã đăng ký.
4. Xác nhận email OTP tới nơi và hết hạn sau hai phút.
5. Nhập OTP sai ba lần và xác nhận mã bị thu hồi.
6. Reset thành công và xác nhận session cũ không còn dùng được.

Không đưa giá trị OTP vào issue tracker, ảnh chụp màn hình, CloudWatch log hoặc
báo cáo dự án.
