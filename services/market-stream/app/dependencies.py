"# Dependencies for FastAPI routes."

from fastapi import Depends, Request

from .broadcaster import QuoteBroadcaster
from .storage import QuoteStore


def get_quote_store(request: Request) -> QuoteStore:
    return request.app.state.quote_store  # type: ignore[attr-defined]


def get_broadcaster(request: Request) -> QuoteBroadcaster:
    return request.app.state.quote_broadcaster  # type: ignore[attr-defined]

