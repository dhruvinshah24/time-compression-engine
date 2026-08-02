"""Configuration settings."""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Time Compression Engine API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    # No default: must be set in .env or environment variable.
    # Example: postgresql+asyncpg://user:password@localhost:5432/tce
    DATABASE_URL: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
