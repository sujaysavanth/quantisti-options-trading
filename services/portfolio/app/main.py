"""Portfolio management service.

Purpose:
    - Manages accounts, positions, and trade history.
Planned endpoints (stubs):
    - /v1/accounts
    - /v1/positions
    - /v1/trades
"""

from fastapi import FastAPI

from .routers import health

app = FastAPI(title="Portfolio Service")

# TODO: Connect to persistence layer for account state.
app.include_router(health.router, prefix="/health")


# TODO: Add background tasks for syncing portfolio data.
