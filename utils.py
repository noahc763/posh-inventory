import os
import imghdr
from werkzeug.utils import secure_filename
from flask import current_app

ALLOWED_EXTS = {"jpg", "jpeg", "png", "gif", "webp"}

def _is_image(path: str) -> bool:
    # imghdr is simple/quick; good enough for gatekeeping
    kind = imghdr.what(path)
    return kind in {"jpeg", "png", "gif", "webp"}

def save_upload(file_storage):
    """
    Saves the uploaded image to <static>/uploads and returns a *relative* path:
    e.g. 'uploads/abc123.jpg'. Returns None if invalid.
    """
    if not file_storage:
        return None

    filename = secure_filename(file_storage.filename or "")
    if not filename:
        return None

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTS:
        return None

    # Unique-ish name to avoid collisions
    base, _ = os.path.splitext(filename)
    unique = os.urandom(8).hex()
    final_name = f"{base}-{unique}.{ext}"

    upload_dir = current_app.config.get("UPLOAD_FOLDER")
    if not upload_dir:
        # Fallback to static/uploads if not configured
        upload_dir = os.path.join(current_app.static_folder, "uploads")
        os.makedirs(upload_dir, exist_ok=True)

    abs_path = os.path.join(upload_dir, final_name)
    file_storage.save(abs_path)

    # Sanity check: make sure it’s an image
    if not _is_image(abs_path):
        try:
            os.remove(abs_path)
        except OSError:
            pass
        return None

    # Return *relative* path for templates: 'uploads/<file>'
    return f"uploads/{final_name}"
