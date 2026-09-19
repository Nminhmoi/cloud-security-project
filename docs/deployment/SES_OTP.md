# Khôi phục mật khẩu bằng OTP qua Amazon SES

Khi chạy thử trên máy cá nhân, bạn có thể dùng `OTP_DELIVERY_MODE=local`. Trên AWS, ứng dụng dùng chế độ `ses` nếu đã cấu hình `ses_sender_email`; nếu chưa có địa chỉ gửi, chế độ sẽ là `disabled`. Khi đó, quá trình khôi phục mật khẩu dừng lại nhưng phản hồi trên trình duyệt vẫn giữ nguyên. Giá trị OTP không được ghi vào log trên AWS.

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

EC2 instance vai trò chỉ được gửi từ identity do Terraform quản lý. Boto3 sử dụng
thông tin xác thực tạm thời của instance profile; không lưu AWS access key trong
`.env` hoặc container.

## SES sandbox

Khi AWS account còn trong SES sandbox, địa chỉ nhận cũng phải được xác minh, trừ
khi dùng mailbox simulator. Nếu phục vụ người dùng thật, cần yêu cầu production
access trong SES console và chỉ bật gửi tại AWS Region dự kiến.

## Kiểm thử nhanh

1. Xác minh địa chỉ gửi và địa chỉ nhận nếu còn trong sandbox.
2. Mở `/forgot-password` qua ALB.
3. Gửi email đã đăng ký.
4. Xác nhận email OTP tới nơi và hết hạn sau hai phút.
5. Nhập OTP sai ba lần và xác nhận mã bị thu hồi.
6. Đặt lại mật khẩu thành công và xác nhận phiên đăng nhập cũ không còn dùng được.

Không đưa giá trị OTP vào issue tracker, ảnh chụp màn hình, CloudWatch log hoặc
báo cáo dự án.
