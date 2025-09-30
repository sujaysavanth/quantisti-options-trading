"""Explainability service.

Purpose:
    - Provides transparency and interpretability for model predictions.
Planned endpoints (stubs):
    - /v1/explain/shap
    - /v1/explain/lime
    - /v1/explain/global
"""

from fastapi import FastAPI

from .routers import health

app = FastAPI(title="Explain Service")

# TODO: Integrate explainability libraries and data sources.
app.include_router(health.router, prefix="/health")


# TODO: Add async workers for heavy explainability computations.
