import os
import tempfile
import zipfile
from uuid import uuid4

from flask import current_app, send_file, send_from_directory
from werkzeug.utils import secure_filename


ALLOWED_MIME_TYPES = {
    "pdf": {"application/pdf"},
    "txt": {"text/plain"},
    "csv": {"text/csv", "application/vnd.ms-excel"},
    "png": {"image/png"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
    "xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    },
    "pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/octet-stream",
    },
    "zip": {
        "application/zip",
        "application/x-zip-compressed",
        "application/octet-stream",
    },
}

FILE_SIGNATURES = {
    "pdf": (b"%PDF-",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "zip": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
}


def _bucket_name():
    return current_app.config.get("AWS_S3_BUCKET")


def _s3_client():
    import boto3

    return boto3.client("s3", region_name=current_app.config["AWS_REGION"])


def _download_name(stored_filename):
    basename = os.path.basename(stored_filename)
    parts = basename.split("_", 1)
    return parts[1] if len(parts) == 2 else basename


def validate_upload(file):
    """Validate filename, declared content type, and actual stream size."""

    safe_name = secure_filename(file.filename or "")
    if not safe_name or "." not in safe_name:
        raise ValueError("Tên tệp hoặc phần mở rộng không hợp lệ")

    extension = safe_name.rsplit(".", 1)[1].lower()
    allowed_extensions = current_app.config["ALLOWED_UPLOAD_EXTENSIONS"]
    if extension not in allowed_extensions or extension not in ALLOWED_MIME_TYPES:
        raise ValueError("Loại tệp không được phép")

    mimetype = (file.mimetype or "").lower()
    if mimetype not in ALLOWED_MIME_TYPES[extension]:
        raise ValueError("Định dạng nội dung không khớp với phần mở rộng")

    current_position = file.stream.tell()
    file.stream.seek(0)
    header = file.stream.read(8192)
    file.stream.seek(0)
    if extension in FILE_SIGNATURES and not header.startswith(FILE_SIGNATURES[extension]):
        file.stream.seek(current_position)
        raise ValueError("Chữ ký nội dung không khớp với loại tệp")
    if extension in {"txt", "csv"} and b"\x00" in header:
        file.stream.seek(current_position)
        raise ValueError("Tệp văn bản chứa dữ liệu nhị phân không hợp lệ")
    if extension in {"docx", "xlsx", "pptx"}:
        expected_directory = {"docx": "word/", "xlsx": "xl/", "pptx": "ppt/"}[
            extension
        ]
        try:
            with zipfile.ZipFile(file.stream) as office_archive:
                members = office_archive.namelist()
                valid_office_file = "[Content_Types].xml" in members and any(
                    name.startswith(expected_directory) for name in members
                )
        except (OSError, zipfile.BadZipFile):
            valid_office_file = False
        finally:
            file.stream.seek(0)
        if not valid_office_file:
            file.stream.seek(current_position)
            raise ValueError("Cấu trúc tệp Office không hợp lệ")

    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(current_position)
    if size <= 0:
        raise ValueError("Không thể tải lên tệp rỗng")
    if size > current_app.config["MAX_CONTENT_LENGTH"]:
        raise ValueError("Tệp tải lên quá lớn")
    return size


def save_upload(file, user_id):
    filename = secure_filename(file.filename) or "upload"
    stored_filename = f"{user_id}/{uuid4().hex}_{filename}"

    if _bucket_name():
        file.stream.seek(0)
        extra_args = {"ServerSideEncryption": "AES256"}
        if file.mimetype:
            extra_args["ContentType"] = file.mimetype
        _s3_client().upload_fileobj(
            file.stream,
            _bucket_name(),
            stored_filename,
            ExtraArgs=extra_args,
        )
        return stored_filename

    os.makedirs(current_app.config["UPLOAD_FOLDER"], exist_ok=True)
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], stored_filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    file.save(path)
    return stored_filename


def send_stored_file(filename):
    if _bucket_name():
        temporary_file = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
        _s3_client().download_fileobj(_bucket_name(), filename, temporary_file)
        temporary_file.seek(0)
        return send_file(
            temporary_file,
            as_attachment=True,
            download_name=_download_name(filename),
        )

    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        filename,
        as_attachment=True,
        download_name=_download_name(filename),
    )


def delete_stored_file(filename):
    if _bucket_name():
        _s3_client().delete_object(Bucket=_bucket_name(), Key=filename)
        return

    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    if os.path.isfile(path):
        os.remove(path)

