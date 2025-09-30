"""Health check endpoints for the machine learning service."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", tags=["health"])
async def readyz() -> dict[str, str]:
    return {"status": "ready"}
