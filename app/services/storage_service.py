import os
from flask import current_app, send_from_directory
from werkzeug.utils import secure_filename


def save_upload(file, user_id):
    filename = secure_filename(file.filename)
    stored_filename = f"{user_id}_{filename}"
    os.makedirs(current_app.config["UPLOAD_FOLDER"], exist_ok=True)
    file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], stored_filename))
    return stored_filename


def send_stored_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename, as_attachment=True)


def delete_stored_file(filename):
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    if os.path.isfile(path):
        os.remove(path)

