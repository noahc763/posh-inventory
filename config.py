# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Secrets
    SECRET_KEY = (
        os.getenv("SECRET_KEY")
        or os.getenv("FLASK_SECRET")
        or "dev-secret"  # change in production
    )

    # Uploads
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "8000000"))
    ALLOWED_EXTENSIONS = set(os.getenv("ALLOWED_EXTENSIONS", "jpg,jpeg,png,webp").split(","))

    # SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database URL (Render sets DATABASE_URL)
    _db = os.getenv("DATABASE_URL")
    if _db and _db.startswith("postgres://"):
        _db = _db.replace("postgres://", "postgresql://", 1)

    # Fallback for local dev (use one filename consistently)
    SQLALCHEMY_DATABASE_URI = _db or "sqlite:///posh.db"

    # Optional: nicer behavior on Render/PG
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
