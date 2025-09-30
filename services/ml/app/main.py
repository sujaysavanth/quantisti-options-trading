"""Machine learning inference service.

Purpose:
    - Hosts predictive models for risk and strategy recommendations.
Planned endpoints (stubs):
    - /v1/predict
    - /v1/model/info
    - /v1/model/reload
"""

from fastapi import FastAPI

from .routers import health

app = FastAPI(title="ML Service")

# TODO: Load models and configure feature pipelines.
app.include_router(health.router, prefix="/health")


# TODO: Add model lifecycle management when models are available.
