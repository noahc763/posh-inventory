# config.py
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

class Config:
    # Secrets
    SECRET_KEY = (
        os.getenv("SECRET_KEY")
        or os.getenv("FLASK_SECRET")
        or "dev-secret"  # change in production
    )

    # Uploads
    # Folder name inside /static (configurable): e.g. "uploads"
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
    # Absolute folder on disk where files are saved
    UPLOAD_FOLDER = os.path.join(STATIC_DIR, UPLOAD_DIR)
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "8000000"))  # 8MB
    ALLOWED_EXTENSIONS = set(os.getenv("ALLOWED_EXTENSIONS", "jpg,jpeg,png,webp").split(","))

    # SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database URL (Render sets DATABASE_URL)
    _db = os.getenv("DATABASE_URL")
    if _db and _db.startswith("postgres://"):
        _db = _db.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db or "sqlite:///posh.db"

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

