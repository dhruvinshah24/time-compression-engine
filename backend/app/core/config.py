"""Configuration settings."""
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    PROJECT_NAME: str = "Time Compression Engine API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    # No default: must be set in .env or environment variable.
    # Example: postgresql+asyncpg://user:password@localhost:5432/tce
    DATABASE_URL: str = ""
    NIGHT_VISION_WEIGHTS: str = str(
        Path(__file__).resolve().parents[2] / "models" / "nightvision-unisv-five-v1.pt"
    )

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
