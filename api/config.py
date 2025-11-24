"""
Configuration settings for the Surf Tracker API.
Uses pydantic-settings for type-safe environment variable management.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Database
    DATABASE_URL: str = "postgresql://surf_user:changeme@db:5432/surf_tracker"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # JWT Authentication
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Email (SMTP)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    # File Upload
    MAX_UPLOAD_SIZE_MB: int = 500
    ALLOWED_VIDEO_EXTENSIONS: List[str] = [".mp4", ".mov", ".avi", ".mkv"]

    # Data paths
    DATA_DIR: str = "/data"
    QUEUE_DIR: str = "/data/queue"
    OUTPUT_DIR: str = "/data/output"
    PROFILE_PICTURES_DIR: str = "/data/profile_pictures"


# Global settings instance
settings = Settings()
