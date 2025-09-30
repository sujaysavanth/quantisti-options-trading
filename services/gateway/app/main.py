"""Gateway service.

Purpose:
    - Acts as the API gateway and auth boundary for downstream services.
Planned endpoints (stubs):
    - /v1/auth/login
    - /v1/routes/market
    - /v1/routes/portfolio
"""

from fastapi import FastAPI

from .routers import health

app = FastAPI(title="Gateway Service")

# TODO: Configure logging, middleware, and Firebase integrations.
# TODO: Inject Firebase JWT verification dependency hooks before routing to downstream services.
app.dependency_overrides = {}

app.include_router(health.router, prefix="/health")


# TODO: Implement startup and shutdown events when real dependencies are added.
