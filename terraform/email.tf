# --- Gửi email đặt lại mật khẩu ---
# Địa chỉ email định danh nhận được thư xác minh sau lần áp dụng đầu tiên.
# SES chỉ có thể gửi từ địa chỉ này sau khi chủ sở hữu nhấp vào liên kết xác minh.
resource "aws_ses_email_identity" "otp" {
  count = local.ses_enabled ? 1 : 0
  email = var.ses_sender_email
}
