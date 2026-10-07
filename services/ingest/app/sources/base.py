"""What every option-chain source returns, and the interface it implements."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Protocol


@dataclass(frozen=True)
class ChainQuote:
    """One option contract at one moment."""

    expiry: date
    option_type: str                     # 'C' or 'P'
    strike: float
    bid: Optional[float]
    ask: Optional[float]
    last: Optional[float]
    volume: Optional[int]
    open_interest: Optional[int]         # None when the source doesn't provide it (Yahoo)
    vendor_iv: Optional[float] = None    # the source's own IV/delta, kept for comparison only
    vendor_delta: Optional[float] = None


@dataclass(frozen=True)
class ChainSnapshot:
    """A whole chain as captured in one fetch."""

    symbol: str                          # 'SPX'
    source: str                          # 'cboe', 'yahoo', ...
    delay_minutes: int                   # how stale the quotes are by the source's terms
    quoted_at: datetime                  # when the quotes are from (timezone-aware)
    session_date: date                   # the trading session they belong to
    underlying_price: Optional[float]    # spot at quoted_at, if the source gives it
    quotes: List[ChainQuote] = field(default_factory=list)


class ChainSource(Protocol):
    """Anything that can fetch an SPX option chain. Paid providers plug in here."""

    name: str
    delay_minutes: int

    def fetch_chain(self, expiries: int, moneyness: float) -> ChainSnapshot:
        """The nearest `expiries` expiries, strikes within +/- `moneyness` of spot."""
        ...
