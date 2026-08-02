"""Configuration settings."""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Time Compression Engine API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tce"
    
    class Config:
        env_file = ".env"

settings = Settings()
