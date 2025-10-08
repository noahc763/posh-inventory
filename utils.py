# utils.py
import os
from werkzeug.utils import secure_filename
from flask import current_app
from uuid import uuid4


def allowed_file(filename: str) -> bool:
    """Check if the file extension is allowed."""
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config.get("ALLOWED_EXTENSIONS", {"jpg", "jpeg", "png", "webp"})


def save_upload(file_storage) -> str | None:
    """Save an uploaded file to the configured UPLOAD_DIR and return relative path."""
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        return None

    upload_dir = os.path.join(current_app.static_folder, current_app.config["UPLOAD_DIR"])
    os.makedirs(upload_dir, exist_ok=True)

    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    fname = f"{uuid4().hex}.{ext}"
    safe_name = secure_filename(fname)
    path = os.path.join(upload_dir, safe_name)
    file_storage.save(path)

    # Return path relative to static/ so it can be served by url_for("static", filename=...)
    return os.path.join(current_app.config["UPLOAD_DIR"], safe_name)
