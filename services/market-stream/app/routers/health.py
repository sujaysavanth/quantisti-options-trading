"""Health endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz", tags=["health"])
async def healthz():
    return {"status": "ok"}
