"""Risk and analytics service.

Purpose:
    - Computes risk metrics and performance statistics.
Planned endpoints (stubs):
    - /v1/risk/sharpe
    - /v1/risk/var
    - /v1/performance/summary
"""

from fastapi import FastAPI

from .routers import health

app = FastAPI(title="Stats Service")

# TODO: Integrate analytics libraries and data stores.
app.include_router(health.router, prefix="/health")


# TODO: Add background jobs for periodic risk calculations.
