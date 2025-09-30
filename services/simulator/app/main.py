"""Strategy simulator service.

Purpose:
    - Runs option strategy backtests and scenario simulations.
Planned endpoints (stubs):
    - /v1/simulate/bull-call
    - /v1/simulate/iron-condor
    - /v1/simulate/custom
"""

from fastapi import FastAPI

from .routers import health

app = FastAPI(title="Simulator Service")

# TODO: Integrate portfolio valuation engines and scenario runners.
app.include_router(health.router, prefix="/health")


# TODO: Register background workers when simulation engine is ready.
