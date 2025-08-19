import os
from werkzeug.utils import secure_filename
from flask import current_app

from uuid import uuid4

def allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit('.', 1)[-1].lower()
    return ext in current_app.config['ALLOWED_EXTENSIONS']

def save_upload(file_storage) -> str | None:
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        return None
    os.makedirs(current_app.config['UPLOAD_DIR'], exist_ok=True)
    ext = file_storage.filename.rsplit('.', 1)[-1].lower()
    fname = f"{uuid4().hex}.{ext}"
    path = os.path.join(current_app.config['UPLOAD_DIR'], secure_filename(fname))
    file_storage.save(path)
    return path
