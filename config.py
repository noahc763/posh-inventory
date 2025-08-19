import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///posh.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "8000000"))
    ALLOWED_EXTENSIONS = set((os.getenv("ALLOWED_EXTENSIONS", "jpg,jpeg,png,webp").split(",")))
