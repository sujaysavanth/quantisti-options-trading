"""Configuration settings for ML Features service."""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Service info
    SERVICE_NAME: str = "ML Features Service"
    VERSION: str = "0.1.0"
    ENV: str = os.getenv("ENV", "development")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://quantisti:quantisti@localhost:5432/quantisti"
    )

    # Market Data Service URL (for fetching historical data)
    MARKET_SERVICE_URL: str = os.getenv(
        "MARKET_SERVICE_URL",
        "http://market:8081"
    )

    # Feature computation settings
    LOOKBACK_PERIODS: dict = {
        "short": 10,    # 10 days
        "medium": 20,   # 20 days
        "long": 50      # 50 days
    }

    # Default underlying symbols
    DEFAULT_SYMBOLS: list = ["NIFTY", "BANKNIFTY"]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
