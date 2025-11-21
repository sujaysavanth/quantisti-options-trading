"""Configuration for market-stream service."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "Market Stream Service"
    VERSION: str = "0.1.0"
    ENV: str = "development"
    PORT: int = 8090
    MAX_CONNECTIONS: int = 500

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
