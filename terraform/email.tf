# --- Password-reset email delivery ---
# An email identity receives a verification message after the first apply.
# SES cannot send from it until the owner clicks that verification link.
resource "aws_ses_email_identity" "otp" {
  count = local.ses_enabled ? 1 : 0
  email = var.ses_sender_email
}
