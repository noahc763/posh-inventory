# utils.py
import os
from uuid import uuid4
from werkzeug.utils import secure_filename
from flask import current_app

try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


def allowed_file(filename: str) -> bool:
    """Check if the file extension is allowed."""
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config.get("ALLOWED_EXTENSIONS", {"jpg", "jpeg", "png", "webp"})


def _dest_dir() -> str:
    # Save under static/uploads (so files are served by url_for('static', ...))
    return os.path.join(current_app.static_folder, current_app.config["UPLOAD_DIR"])


def save_upload(file_storage) -> str | None:
    """
    Save an uploaded image into static/uploads and return a path relative to /static (e.g. 'uploads/abc.jpg').
    If Pillow is installed, downscale to max 1600px on the longest edge and compress.
    """
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        return None

    os.makedirs(_dest_dir(), exist_ok=True)

    # Choose extension
    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    if ext == "jpeg":
        ext = "jpg"

    # Generate a safe filename
    fname = f"{uuid4().hex}.{ext}"
    safe_name = secure_filename(fname)
    abs_path = os.path.join(_dest_dir(), safe_name)

    # If Pillow is available, compress/resize
    if PIL_AVAILABLE:
        try:
            img = Image.open(file_storage.stream).convert("RGB")
            img.thumbnail((1600, 1600))  # keep aspect ratio, limit longest edge to 1600
            if ext in ("jpg", "jpeg"):
                img.save(abs_path, format="JPEG", quality=85, optimize=True, progressive=True)
            elif ext == "png":
                img.save(abs_path, format="PNG", optimize=True)
            elif ext == "webp":
                img.save(abs_path, format="WEBP", quality=85, method=6)
            else:
                # fallback to jpg
                alt = os.path.join(_dest_dir(), secure_filename(f"{uuid4().hex}.jpg"))
                img.save(alt, format="JPEG", quality=85, optimize=True, progressive=True)
                rel = os.path.join(current_app.config["UPLOAD_DIR"], os.path.basename(alt))
                return rel
            return os.path.join(current_app.config["UPLOAD_DIR"], safe_name)
        except Exception:
            # If Pillow fails, just save original
            file_storage.stream.seek(0)

    # Plain save (no Pillow)
    file_storage.save(abs_path)
    return os.path.join(current_app.config["UPLOAD_DIR"], safe_name)
