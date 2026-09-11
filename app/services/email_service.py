import smtplib
from email.message import EmailMessage

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import current_app


class EmailDeliveryError(RuntimeError):
    """Raised when an OTP message cannot be delivered safely."""


def _message_content(otp):
    subject = "Mã OTP khôi phục mật khẩu"
    body = f"Mã OTP của bạn là: {otp}\n\nMã có hiệu lực trong 2 phút."
    return subject, body


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

    if delivery_mode == "disabled":
        raise EmailDeliveryError("Dịch vụ gửi OTP chưa được cấu hình")

    subject, body = _message_content(otp)
    if delivery_mode == "ses":
        sender = current_app.config.get("AWS_SES_SENDER")
        if not sender:
            raise EmailDeliveryError("Thiếu cấu hình AWS_SES_SENDER")
        try:
            response = boto3.client(
                "ses",
                region_name=current_app.config["AWS_REGION"],
            ).send_email(
                Source=sender,
                Destination={"ToAddresses": [recipient]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": body, "Charset": "UTF-8"},
                    },
                },
            )
        except (BotoCoreError, ClientError) as error:
            raise EmailDeliveryError("AWS SES không thể gửi OTP") from error
        if not response.get("MessageId"):
            raise EmailDeliveryError("AWS SES không trả về mã xác nhận gửi")
        current_app.logger.info(
            "OTP email accepted by SES for recipient domain %s",
            recipient.rpartition("@")[2],
        )
        return

    if delivery_mode != "smtp":
        raise EmailDeliveryError(
            "OTP_DELIVERY_MODE chỉ chấp nhận local, smtp, ses hoặc disabled"
        )

    username = current_app.config.get("SMTP_USERNAME")
    password = current_app.config.get("SMTP_PASSWORD")
    sender = current_app.config.get("SMTP_FROM") or username

    if not username or not password or not sender:
        raise EmailDeliveryError("Thiếu cấu hình SMTP")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(body)

    try:
        with smtplib.SMTP(
            current_app.config["SMTP_HOST"],
            current_app.config["SMTP_PORT"],
            timeout=15,
        ) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise EmailDeliveryError("SMTP không thể gửi OTP") from error
