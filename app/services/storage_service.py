import os
import tempfile
from uuid import uuid4

from flask import current_app, send_file, send_from_directory
from werkzeug.utils import secure_filename


def _bucket_name():
    return current_app.config.get("AWS_S3_BUCKET")


def _s3_client():
    import boto3

    return boto3.client("s3", region_name=current_app.config["AWS_REGION"])


def _download_name(stored_filename):
    basename = os.path.basename(stored_filename)
    parts = basename.split("_", 1)
    return parts[1] if len(parts) == 2 else basename


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

