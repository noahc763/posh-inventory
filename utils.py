# utils.py
import os
import uuid
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import current_app

# Pillow for safe image handling in Py 3.13+ (imghdr removed)
from PIL import Image, ImageOps

# Allowed extensions you'll accept from users
ALLOWED_EXTS = {"jpg", "jpeg", "png", "webp", "gif", "bmp", "tiff"}

def _allowed_ext(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext in ALLOWED_EXTS

def save_upload(storage_file) -> str | None:
    """
    Save an uploaded image to /static/uploads/, normalizing orientation and format.
    Returns a path relative to the static root, e.g. "uploads/abc123.jpg",
    or None if invalid.

    Requirements: Pillow installed.
    """
    if not storage_file or not getattr(storage_file, "filename", None):
        return None

    filename = storage_file.filename
    if not _allowed_ext(filename):
        # Still attempt to open via PIL; reject if it’s not a real image
        pass

    # Ensure target folder exists
    static_folder = current_app.static_folder  # e.g. <app>/static
    upload_root = os.path.join(static_folder, "uploads")
    os.makedirs(upload_root, exist_ok=True)

    # Use a random filename to avoid collisions; keep jpg output for broad compatibility
    out_name = f"{uuid.uuid4().hex}.jpg"
    out_rel = os.path.join("uploads", out_name)
    out_abs = os.path.join(upload_root, out_name)

    try:
        # Open with PIL to validate content and normalize orientation
        # Image.open() will raise if the content is not a supported image
        with Image.open(storage_file.stream) as im:
            # Auto-orient using EXIF
            im = ImageOps.exif_transpose(im)

            # Convert to RGB for JPEG if needed (avoid saving CMYK/LA/P modes)
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")

            # Save as JPEG, reasonable quality; strip metadata by default
            im.save(out_abs, format="JPEG", quality=85, optimize=True)
    except Exception:
        return None

    # Return path relative to /static so templates can: url_for("static", filename=out_rel)
    return out_rel
