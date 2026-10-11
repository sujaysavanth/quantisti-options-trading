"""Configuration settings for the portfolio service."""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "Portfolio"
    VERSION: str = "0.1.0"
    ENV: str = os.getenv("ENV", "development")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://quantisti:quantisti@localhost:5432/quantisti")

    # The simulator owns the paper trades; this service reads them over HTTP.
    SIMULATOR_URL: str = os.getenv("SIMULATOR_URL", "http://simulator:8082")
    MARKET_STREAM_URL: str = os.getenv("MARKET_STREAM_URL", "http://market_stream:8090")

    SNAPSHOTS_ENABLED: bool = True
    SNAPSHOT_CHECK_SECONDS: int = 60

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
