"""Market data service.

Purpose:
    - Provides market and options reference data for other services.
Planned endpoints (stubs):
    - /v1/candles
    - /v1/option-chain
    - /v1/greeks
"""

from fastapi import FastAPI

from .routers import health

app = FastAPI(title="Market Service")

# TODO: Wire in data providers and caching layers.
app.include_router(health.router, prefix="/health")


# TODO: Implement startup/shutdown when real dependencies exist.
