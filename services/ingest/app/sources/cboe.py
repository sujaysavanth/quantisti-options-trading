"""CBOE's free data: the delayed SPX chain (with open interest) and VIX daily history."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx

from .. import market_spec
from .base import ChainQuote, ChainSnapshot
from .occ import parse_occ
from .session import session_for

CHAIN_URL = "https://cdn-api.cboe.com/api/global/delayed_quotes/options/_SPX.json"
VIX_HISTORY_URL = "https://cdn-api.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; QuantistiIngest/1.0)"}


def _price(value: Any):
    """CBOE uses 0 for 'no bid' / 'no trade'; store that as missing, not as a $0 price."""
    return float(value) if value else None


def _int(value: Any):
    return int(value) if value is not None else None


def parse_chain(payload: Dict[str, Any], expiries: int, moneyness: float) -> ChainSnapshot:
    data = payload["data"]
    spot = float(data["current_price"])
    # last_trade_time is New York time and already ~15 min behind; it says how old the quotes are.
    quoted_at = datetime.fromisoformat(data["last_trade_time"]).replace(tzinfo=market_spec.TZ).astimezone(timezone.utc)
    session = session_for(quoted_at)

    # Third-Friday expiries list both SPX (AM-settled) and SPXW (PM-settled) at the same strikes.
    # Keep SPXW, which matches our 16:00 settlement; use SPX only where no SPXW exists (far LEAPS).
    parsed = [(parse_occ(o["option"]), o) for o in data["options"]]
    weekly_expiries = {s.expiry for s, _ in parsed if s.root == "SPXW"}
    usable = [(s, o) for s, o in parsed if s.root == "SPXW" or s.expiry not in weekly_expiries]

    # An expiry is live until its 16:00 ET close; after that it has settled (e.g. a 0DTE seen at 17:00).
    live = {s.expiry for s, _ in usable if s.expiry > session or (s.expiry == session and market_spec.session_close(session) > quoted_at)}
    keep_expiries = sorted(live)[:expiries]
    lo, hi = spot * (1 - moneyness), spot * (1 + moneyness)

    quotes: List[ChainQuote] = [
        ChainQuote(
            expiry=s.expiry, option_type=s.option_type, strike=s.strike,
            bid=_price(o.get("bid")), ask=_price(o.get("ask")), last=_price(o.get("last_trade_price")),
            volume=_int(o.get("volume")), open_interest=_int(o.get("open_interest")),
            vendor_iv=o.get("iv") or None,   # CBOE sends iv 0 when it couldn't compute one
            vendor_delta=o.get("delta"),
        )
        for s, o in usable
        if s.expiry in keep_expiries and lo <= s.strike <= hi
    ]
    quotes.sort(key=lambda q: (q.expiry, q.strike, q.option_type))
    return ChainSnapshot("SPX", "cboe", 15, quoted_at, session, spot, quotes)


class CboeDelayedSource:
    name = "cboe"
    delay_minutes = 15

    def __init__(self, get: Callable[[str], Dict[str, Any]] | None = None):
        # Injectable so tests can pass a saved payload instead of hitting the network.
        self._get = get or (lambda url: httpx.get(url, headers=HEADERS, timeout=60, follow_redirects=True).raise_for_status().json())

    def fetch_chain(self, expiries: int, moneyness: float) -> ChainSnapshot:
        return parse_chain(self._get(CHAIN_URL), expiries, moneyness)


# ---------------------------------------------------------------- VIX history

@dataclass(frozen=True)
class DailyClose:
    date: date
    close: float


INDEX_HISTORY_URL = "https://cdn-api.cboe.com/api/global/us_indices/daily_prices/{symbol}_History.csv"


def parse_index_history(text: str, start: Optional[date] = None, end: Optional[date] = None) -> List[DailyClose]:
    """A CBOE index history CSV, DATE as MM/DD/YYYY. Two layouts exist: DATE,OPEN,HIGH,LOW,CLOSE (VIX, VIX9D,
    VIX3M) and DATE,<SYMBOL> with just the close (VVIX, SKEW). Keeps rows in [start, end]."""
    reader = csv.DictReader(io.StringIO(text))
    value_col = "CLOSE" if "CLOSE" in (reader.fieldnames or []) else (reader.fieldnames or ["", ""])[-1]
    rows = []
    for row in reader:
        day = datetime.strptime(row["DATE"].strip(), "%m/%d/%Y").date()
        value = (row.get(value_col) or "").strip()
        if (start and day < start) or (end and day > end) or not value:
            continue
        rows.append(DailyClose(day, float(value)))
    return rows


parse_vix_history = parse_index_history      # VIX is one of them; the old name stays for existing callers


def _get_text(url: str) -> str:
    return httpx.get(url, headers=HEADERS, timeout=60, follow_redirects=True).raise_for_status().text


def fetch_index_history(symbol: str, start: Optional[date] = None, end: Optional[date] = None,
                        get_text: Callable[[str], str] | None = None) -> List[DailyClose]:
    return parse_index_history((get_text or _get_text)(INDEX_HISTORY_URL.format(symbol=symbol)), start, end)


def fetch_vix_history(start: Optional[date] = None, end: Optional[date] = None,
                      get_text: Callable[[str], str] | None = None) -> List[DailyClose]:
    return parse_index_history((get_text or _get_text)(VIX_HISTORY_URL), start, end)
