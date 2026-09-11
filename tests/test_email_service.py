import os
import sys
import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError
from flask import Flask


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_ROOT = os.path.join(PROJECT_ROOT, "app")
sys.path.insert(0, APP_ROOT)

from services.email_service import EmailDeliveryError, send_otp_email  # noqa: E402


class EmailServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            OTP_DELIVERY_MODE="ses",
            AWS_REGION="ap-southeast-1",
            AWS_SES_SENDER="verified@example.com",
        )

    @patch("services.email_service.boto3.client")
    def test_ses_sends_utf8_otp_email(self, client_factory):
        ses = Mock()
        ses.send_email.return_value = {"MessageId": "message-123"}
        client_factory.return_value = ses

        with self.app.app_context():
            send_otp_email("recipient@example.com", "123456")

        client_factory.assert_called_once_with("ses", region_name="ap-southeast-1")
        request = ses.send_email.call_args.kwargs
        self.assertEqual(request["Source"], "verified@example.com")
        self.assertEqual(request["Destination"], {"ToAddresses": ["recipient@example.com"]})
        self.assertIn("123456", request["Message"]["Body"]["Text"]["Data"])
        self.assertEqual(request["Message"]["Subject"]["Charset"], "UTF-8")

    @patch("services.email_service.boto3.client")
    def test_ses_error_is_wrapped_without_exposing_provider_details(self, client_factory):
        client_factory.return_value.send_email.side_effect = ClientError(
            {"Error": {"Code": "MessageRejected", "Message": "not verified"}},
            "SendEmail",
        )
        with self.app.app_context():
            with self.assertRaisesRegex(EmailDeliveryError, "AWS SES"):
                send_otp_email("recipient@example.com", "123456")

    def test_disabled_mode_fails_closed(self):
        self.app.config["OTP_DELIVERY_MODE"] = "disabled"
        with self.app.app_context():
            with self.assertRaisesRegex(EmailDeliveryError, "chưa được cấu hình"):
                send_otp_email("recipient@example.com", "123456")


if __name__ == "__main__":
    unittest.main()
