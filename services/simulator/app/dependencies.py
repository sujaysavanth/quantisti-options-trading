"""FastAPI dependencies."""

from fastapi import Request

from .services.market_stream_client import MarketStreamClient
from .services.paper_store import PaperTradeStore


def get_paper_store(request: Request) -> PaperTradeStore:
    return request.app.state.paper_store  # type: ignore[attr-defined]


def get_market_stream_client(_: Request) -> MarketStreamClient:
    # simple factory per-request
    return MarketStreamClient()
