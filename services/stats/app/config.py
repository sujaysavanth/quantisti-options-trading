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
    # Open trades, the account and the capital rules (stress tests) come from the simulator, which owns them.
    SIMULATOR_URL: str = os.getenv("SIMULATOR_URL", "http://simulator:8082")
    # The ml service's GARCH forecast sets today's volatility for filtered historical VaR (EWMA if unavailable).
    ML_URL: str = os.getenv("ML_URL", "http://ml:8085")

    VAR_STORE_ENABLED: bool = True          # store each session's VaR after the close (for the backtests)
    VAR_CHECK_SECONDS: int = 60

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
