import smtplib
from email.message import EmailMessage

from flask import current_app


def send_otp_email(recipient, otp):
    delivery_mode = current_app.config["OTP_DELIVERY_MODE"]

    if delivery_mode == "local":
        current_app.logger.warning(
            "LOCAL OTP for %s: %s (valid for 2 minutes)",
            recipient,
            otp,
        )
        print(
            f"LOCAL OTP for {recipient}: {otp} (valid for 2 minutes)",
            flush=True,
        )
        return

    if delivery_mode != "smtp":
        raise ValueError("OTP_DELIVERY_MODE chỉ chấp nhận 'local' hoặc 'smtp'")

    username = current_app.config.get("SMTP_USERNAME")
    password = current_app.config.get("SMTP_PASSWORD")
    sender = current_app.config.get("SMTP_FROM") or username

    if not username or not password or not sender:
        raise ValueError("Thiếu cấu hình SMTP")

    message = EmailMessage()
    message["Subject"] = "Mã OTP khôi phục mật khẩu"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        f"Mã OTP của bạn là: {otp}\n\n"
        "Mã có hiệu lực trong 2 phút."
    )

    with smtplib.SMTP(
        current_app.config["SMTP_HOST"],
        current_app.config["SMTP_PORT"],
        timeout=15,
    ) as smtp:
        smtp.starttls()
        smtp.login(username, password)
        smtp.send_message(message)
