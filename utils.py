# utils.py
import os
from werkzeug.utils import secure_filename

ALLOWED_EXTS = {"jpg", "jpeg", "png", "webp", "gif"}

def save_upload(file_storage) -> str | None:
    """
    Save to <project>/static/uploads/<filename> and return 'uploads/<filename>'.
    Returns None if disallowed/failed.
    """
    if not file_storage or not file_storage.filename:
        return None

    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTS:
        return None

    # static/uploads path anchored to this file
    here = os.path.dirname(__file__)
    static_dir = os.path.join(here, "static")
    upload_dir = os.path.join(static_dir, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    # de-dupe filename if needed
    base, dot, suf = filename.partition(".")
    suf = suf or "jpg"
    target = os.path.join(upload_dir, filename)
    i = 2
    while os.path.exists(target):
        filename = f"{base}-{i}.{suf}"
        target = os.path.join(upload_dir, filename)
        i += 1

    file_storage.save(target)
    # IMPORTANT: return a path *relative to /static* (no leading slash)
    return f"uploads/{filename}"
