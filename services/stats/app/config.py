"""Configuration settings for the stats service."""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "Stats & Risk"
    VERSION: str = "0.1.0"
    ENV: str = os.getenv("ENV", "development")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://quantisti:quantisti@localhost:5432/quantisti")

    # Positions come from the portfolio service (netted across paper trades), prices from market-stream.
    PORTFOLIO_URL: str = os.getenv("PORTFOLIO_URL", "http://portfolio:8083")
    MARKET_STREAM_URL: str = os.getenv("MARKET_STREAM_URL", "http://market_stream:8090")

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
