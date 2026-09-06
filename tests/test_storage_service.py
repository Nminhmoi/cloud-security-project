import io
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask
from werkzeug.datastructures import FileStorage

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_ROOT = os.path.join(PROJECT_ROOT, "app")
sys.path.insert(0, APP_ROOT)

from services.storage_service import (  # noqa: E402
    delete_stored_file,
    save_upload,
    send_stored_file,
)


class FakeS3Client:
    def __init__(self):
        self.objects = {}
        self.last_extra_args = None

    def upload_fileobj(self, stream, bucket, key, ExtraArgs=None):
        self.objects[(bucket, key)] = stream.read()
        self.last_extra_args = ExtraArgs

    def download_fileobj(self, bucket, key, destination):
        destination.write(self.objects[(bucket, key)])

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)


class StorageServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(
            AWS_REGION="ap-southeast-1",
            AWS_S3_BUCKET="test-documents",
            UPLOAD_FOLDER=self.temp_dir.name,
        )
        self.s3 = FakeS3Client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_s3_upload_download_and_delete(self):
        uploaded = FileStorage(
            stream=io.BytesIO(b"classified"),
            filename="../../report.txt",
            content_type="text/plain",
        )

        with self.app.test_request_context(), patch(
            "services.storage_service._s3_client", return_value=self.s3
        ):
            key = save_upload(uploaded, 42)
            self.assertRegex(key, r"^42/[0-9a-f]{32}_report\.txt$")
            self.assertEqual(
                self.s3.last_extra_args,
                {"ServerSideEncryption": "AES256", "ContentType": "text/plain"},
            )

            response = send_stored_file(key)
            response.direct_passthrough = False
            self.assertEqual(response.get_data(), b"classified")
            self.assertIn("report.txt", response.headers["Content-Disposition"])
            response.close()

            delete_stored_file(key)
            self.assertNotIn(("test-documents", key), self.s3.objects)


if __name__ == "__main__":
    unittest.main()
