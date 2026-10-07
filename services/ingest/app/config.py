"""Settings for the ingest service, read from environment variables (or a .env file)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SERVICE_NAME: str = "Ingest Service"
    PORT: int = 8087

    # Containers reach Kafka at kafka:9092; tools on your machine use localhost:9094.
    KAFKA_BOOTSTRAP: str = "kafka:9092"

    # Start the polling loop with the web app. Turn off to run only the API or the CLI.
    PRODUCERS_ENABLED: bool = True

    # Where option chains come from. Both are free and ~15 minutes delayed;
    # only CBOE includes open interest.
    CHAIN_SOURCE: Literal["cboe", "yahoo"] = "cboe"

    # Polling during market hours.
    INTRADAY_POLL_SECONDS: int = 60
    CHAIN_POLL_SECONDS: int = 90

    # How much of the chain to publish: the nearest N expiries, strikes within +/- this fraction of spot.
    CHAIN_EXPIRIES: int = 5
    CHAIN_MONEYNESS: float = 0.05

    # Stream bridge (python -m app.bridge): where to post quotes, and which expiry to show:
    # the nearest one at least this many calendar days out.
    MARKET_STREAM_URL: str = "http://market_stream:8090"
    BRIDGE_MIN_DTE: int = 1

    # Gap detector + backfill worker: the database it checks, and how often.
    DATABASE_URL: str = "postgresql://quantisti:quantisti@postgres:5432/quantisti"
    GAPS_ENABLED: bool = True
    GAP_SCAN_MINUTES: int = 60          # full scan: find gaps and request backfills
    GAP_RECHECK_SECONDS: int = 120      # cheap pass: mark requested gaps filled once the data is stored


@lru_cache
def get_settings() -> Settings:
    return Settings()
