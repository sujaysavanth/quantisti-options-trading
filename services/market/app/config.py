"""Configuration settings for the Market service."""

import os
from functools import lru_cache


class Settings:
    """Application settings loaded from environment variables."""

    # Service metadata
    SERVICE_NAME: str = "Market Service"
    VERSION: str = "0.1.0"
    ENV: str = os.getenv("ENV", "development")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://quantisti:quantisti@postgres:5432/quantisti"
    )

    # API Settings
    PORT: int = int(os.getenv("PORT", 8081))

    # Black-Scholes defaults
    RISK_FREE_RATE: float = float(os.getenv("RISK_FREE_RATE", "0.065"))  # 6.5% for India
    DIVIDEND_YIELD: float = float(os.getenv("DIVIDEND_YIELD", "0.012"))  # ~1.2% for Nifty

    # Cache settings
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))  # 5 minutes

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
