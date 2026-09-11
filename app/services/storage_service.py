"""Private local/S3 storage helpers with upload validation."""

import hashlib
import os
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import uuid4

from flask import current_app, send_file
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


@dataclass(frozen=True)
class UploadMetadata:
    filename: str
    content_type: str
    size: int
    sha256: str


def _bucket_name():
    return current_app.config.get("AWS_S3_BUCKET")


def _s3_client():
    import boto3

    return boto3.client("s3", region_name=current_app.config["AWS_REGION"])


def _download_name(stored_filename):
    basename = os.path.basename(stored_filename)
    parts = basename.split("_", 1)
    return parts[1] if len(parts) == 2 else basename


def _validate_storage_key(storage_key):
    """Reject absolute, ambiguous, and traversing local paths/S3 keys."""
    if not isinstance(storage_key, str) or not storage_key or "\x00" in storage_key:
        raise ValueError("Storage key không hợp lệ")
    if "\\" in storage_key:
        raise ValueError("Storage key không hợp lệ")
    key_path = PurePosixPath(storage_key)
    if (
        key_path.is_absolute()
        or any(part in {"", ".", ".."} for part in key_path.parts)
        or key_path.as_posix() != storage_key
    ):
        raise ValueError("Storage key không hợp lệ")
    return key_path.as_posix()


def _local_path(storage_key):
    safe_key = _validate_storage_key(storage_key)
    upload_root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    candidate = (upload_root / PurePosixPath(safe_key)).resolve()
    if not candidate.is_relative_to(upload_root):
        raise ValueError("Storage key nằm ngoài thư mục upload")
    return candidate


def _validate_archive(stream, extension):
    try:
        with zipfile.ZipFile(stream) as archive:
            members = archive.infolist()
    except (OSError, zipfile.BadZipFile) as error:
        raise ValueError("Cấu trúc tệp nén không hợp lệ") from error
    finally:
        stream.seek(0)

    if len(members) > current_app.config.get("MAX_ARCHIVE_MEMBERS", 1000):
        raise ValueError("Tệp nén chứa quá nhiều mục")

    total_size = 0
    total_compressed = 0
    for member in members:
        member_name = member.filename
        member_path = PurePosixPath(member_name)
        if (
            not member_name
            or "\\" in member_name
            or member_path.is_absolute()
            or ".." in member_path.parts
        ):
            raise ValueError("Tệp nén chứa đường dẫn không an toàn")
        if member.flag_bits & 0x1:
            raise ValueError("Tệp nén được mã hóa không được hỗ trợ")
        file_type = (member.external_attr >> 16) & 0o170000
        if file_type == stat.S_IFLNK:
            raise ValueError("Tệp nén chứa symbolic link không an toàn")
        total_size += member.file_size
        total_compressed += member.compress_size

    maximum_size = current_app.config.get(
        "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 128 * 1024 * 1024
    )
    if total_size > maximum_size:
        raise ValueError("Dung lượng giải nén vượt giới hạn")
    if total_size:
        ratio = total_size / max(total_compressed, 1)
        maximum_ratio = current_app.config.get("MAX_ARCHIVE_COMPRESSION_RATIO", 100)
        if ratio > maximum_ratio:
            raise ValueError("Tỷ lệ nén bất thường")

    if extension in {"docx", "xlsx", "pptx"}:
        expected_directory = {"docx": "word/", "xlsx": "xl/", "pptx": "ppt/"}[
            extension
        ]
        names = {member.filename for member in members}
        if "[Content_Types].xml" not in names or not any(
            name.startswith(expected_directory) for name in names
        ):
            raise ValueError("Cấu trúc tệp Office không hợp lệ")


def _stream_sha256(stream):
    digest = hashlib.sha256()
    stream.seek(0)
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
    stream.seek(0)
    return digest.hexdigest()


def validate_upload(file):
    """Validate the upload and return trusted metadata for persistence."""
    safe_name = secure_filename(file.filename or "")
    if not safe_name or "." not in safe_name:
        raise ValueError("Tên tệp hoặc phần mở rộng không hợp lệ")
    if len(safe_name) > 180:
        raise ValueError("Tên tệp quá dài")

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
    if extension in FILE_SIGNATURES and not header.startswith(
        FILE_SIGNATURES[extension]
    ):
        file.stream.seek(current_position)
        raise ValueError("Chữ ký nội dung không khớp với loại tệp")
    if extension in {"txt", "csv"} and b"\x00" in header:
        file.stream.seek(current_position)
        raise ValueError("Tệp văn bản chứa dữ liệu nhị phân không hợp lệ")
    if extension in {"zip", "docx", "xlsx", "pptx"}:
        _validate_archive(file.stream, extension)

    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    if size <= 0:
        file.stream.seek(current_position)
        raise ValueError("Không thể tải lên tệp rỗng")
    if size > current_app.config["MAX_CONTENT_LENGTH"]:
        file.stream.seek(current_position)
        raise ValueError("Tệp tải lên quá lớn")

    checksum = _stream_sha256(file.stream)
    file.stream.seek(current_position)
    return UploadMetadata(
        filename=safe_name,
        content_type=mimetype,
        size=size,
        sha256=checksum,
    )


def save_upload(file, user_id, metadata=None):
    filename = (
        metadata.filename
        if metadata
        else secure_filename(file.filename) or "upload"
    )
    stored_filename = f"{user_id}/{uuid4().hex}_{filename}"
    _validate_storage_key(stored_filename)

    if _bucket_name():
        file.stream.seek(0)
        extra_args = {"ServerSideEncryption": "AES256"}
        content_type = metadata.content_type if metadata else file.mimetype
        if content_type:
            extra_args["ContentType"] = content_type
        _s3_client().upload_fileobj(
            file.stream,
            _bucket_name(),
            stored_filename,
            ExtraArgs=extra_args,
        )
        return stored_filename

    path = _local_path(stored_filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    file.stream.seek(0)
    file.save(path)
    return stored_filename


def send_stored_file(filename, download_name=None):
    filename = _validate_storage_key(filename)
    safe_download_name = secure_filename(download_name or _download_name(filename))
    if not safe_download_name:
        safe_download_name = "download"

    if _bucket_name():
        temporary_file = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
        _s3_client().download_fileobj(_bucket_name(), filename, temporary_file)
        temporary_file.seek(0)
        return send_file(
            temporary_file,
            as_attachment=True,
            download_name=safe_download_name,
        )

    return send_file(
        _local_path(filename),
        as_attachment=True,
        download_name=safe_download_name,
    )


def delete_stored_file(filename):
    filename = _validate_storage_key(filename)
    if _bucket_name():
        _s3_client().delete_object(Bucket=_bucket_name(), Key=filename)
        return

    path = _local_path(filename)
    if path.is_file():
        path.unlink()
