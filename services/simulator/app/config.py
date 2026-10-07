"""Configuration settings for Strategy Simulator service."""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Service info
    SERVICE_NAME: str = "Strategy Simulator"
    VERSION: str = "0.1.0"
    ENV: str = os.getenv("ENV", "development")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://quantisti:quantisti@localhost:5432/quantisti"
    )

    # Market Data Service URL (for fetching option prices)
    MARKET_SERVICE_URL: str = os.getenv(
        "MARKET_SERVICE_URL",
        "http://market:8081"
    )

    # Market Stream Service for live quotes
    MARKET_STREAM_URL: str = os.getenv(
        "MARKET_STREAM_URL",
        "http://market_stream:8090"
    )

    # Backtest settings
    DEFAULT_INITIAL_CAPITAL: float = 100_000.0  # USD
    DEFAULT_STRIKE_RANGE: int = 10
    MAX_CONCURRENT_BACKTESTS: int = 5

    # SPX contract multiplier: one contract = 100 x index points
    CONTRACT_MULTIPLIER: int = 100

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
