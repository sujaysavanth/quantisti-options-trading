"""Yahoo Finance: intraday bars for SPX/VIX and a fallback SPX option chain (free, unofficial, rate-limited)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, List, Optional

import pandas as pd

from .. import market_spec
from .base import ChainQuote, ChainSnapshot
from .occ import parse_occ
from .session import session_for

TICKERS = {"SPX": "^GSPC", "VIX": "^VIX"}

# Measured 2026-10-05: how far back each bar size goes, and the longest span one request may cover.
LIMITS = {
    "1m": (timedelta(days=30), timedelta(days=7)),     # Yahoo allows 8 days per request; 7 leaves margin
    "5m": (timedelta(days=60), timedelta(days=30)),
    "1h": (timedelta(days=730), timedelta(days=180)),
}


@dataclass(frozen=True)
class Bar:
    symbol: str
    interval: str
    ts: datetime          # bar start, UTC
    open: float
    high: float
    low: float
    close: float
    volume: int
    source: str = "yahoo"


def _cents(value: Any) -> float:
    """Yahoo returns float32 prices (7730.85986328125); index levels are quoted to the cent."""
    return round(float(value), 2)


BAR_LENGTH = {"1m": timedelta(minutes=1), "5m": timedelta(minutes=5), "1h": timedelta(hours=1)}


def to_bars(df: pd.DataFrame, symbol: str, interval: str) -> List[Bar]:
    """Yahoo DataFrame -> bars that overlap the regular session, in UTC. VIX also trades overnight; those bars are dropped.

    "Overlap", not "start inside": Yahoo aligns VIX hourly bars on the hour, so its 09:00-10:00 bar
    covers the first half hour of the session and is kept (ts stays 09:00, as Yahoo labels it).
    """
    if df.empty:
        return []
    if isinstance(df.columns, pd.MultiIndex):
        df = df.droplevel(1, axis=1)
    length = BAR_LENGTH.get(interval, timedelta(0))
    bars = []
    for ts, row in df.dropna(subset=["Open", "High", "Low", "Close"]).iterrows():
        start = ts.to_pydatetime().astimezone(timezone.utc)
        day = start.astimezone(market_spec.TZ).date()
        opens = datetime.combine(day, datetime.strptime("09:30", "%H:%M").time(), market_spec.TZ)
        if not market_spec.is_trading_day(day) or not (start + length > opens and start < market_spec.session_close(day)):
            continue
        bars.append(Bar(symbol, interval, start, _cents(row["Open"]), _cents(row["High"]), _cents(row["Low"]),
                        _cents(row["Close"]), int(row["Volume"]) if pd.notna(row["Volume"]) else 0))
    return bars


def fetch_bars(symbol: str, interval: str, start: datetime, end: datetime,
               download: Optional[Callable[..., pd.DataFrame]] = None,
               now: Optional[datetime] = None) -> List[Bar]:
    """Bars in [start, end), split into requests Yahoo accepts. Raises if the range is beyond Yahoo's window."""
    import yfinance as yf
    download = download or (lambda **kw: yf.download(progress=False, auto_adjust=False, **kw))
    window, span = LIMITS[interval]
    oldest = (now or datetime.now(timezone.utc)) - window + timedelta(hours=1)
    if end <= oldest:
        raise ValueError(f"{interval} bars before {oldest:%Y-%m-%d} are no longer available from Yahoo")
    start = max(start, oldest)

    bars: List[Bar] = []
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + span, end)
        df = download(tickers=TICKERS[symbol], start=chunk_start, end=chunk_end, interval=interval)
        bars += to_bars(df, symbol, interval)
        chunk_start = chunk_end
    return sorted({b.ts: b for b in bars}.values(), key=lambda b: b.ts)  # dedupe chunk overlaps


# ---------------------------------------------------------------- daily bars

@dataclass(frozen=True)
class DailyBar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


def fetch_daily(symbol: str, start: date, end: date,
                download: Optional[Callable[..., pd.DataFrame]] = None) -> List[DailyBar]:
    """Daily OHLCV for trading days in [start, end]. Today's row is partial until the close."""
    import yfinance as yf
    download = download or (lambda **kw: yf.download(progress=False, auto_adjust=False, **kw))
    df = download(tickers=TICKERS[symbol], start=start, end=end + timedelta(days=1), interval="1d")
    if df.empty:
        return []
    if isinstance(df.columns, pd.MultiIndex):
        df = df.droplevel(1, axis=1)
    return [
        DailyBar(ts.date(), _cents(r["Open"]), _cents(r["High"]), _cents(r["Low"]), _cents(r["Close"]),
                 int(r["Volume"]) if pd.notna(r["Volume"]) else 0)
        for ts, r in df.dropna(subset=["Open", "High", "Low", "Close"]).iterrows()
        if start <= ts.date() <= end
    ]


# ---------------------------------------------------------------- fallback option chain

def _num(value: Any) -> Optional[float]:
    return float(value) if pd.notna(value) and value else None


class YahooDelayedSource:
    """Same shape as CboeDelayedSource. One request per expiry, so slower and easier to rate-limit."""

    name = "yahoo"
    delay_minutes = 15

    def __init__(self, ticker: Any = None, now: Optional[Callable[[], datetime]] = None):
        if ticker is None:
            import yfinance as yf
            ticker = yf.Ticker("^SPX")
        self._ticker = ticker            # injectable so tests can pass a fake
        self._now = now or (lambda: datetime.now(timezone.utc))

    def fetch_chain(self, expiries: int, moneyness: float) -> ChainSnapshot:
        # Yahoo gives no single "as of" time; treat quotes as delay_minutes old, like CBOE's.
        quoted_at = self._now() - timedelta(minutes=self.delay_minutes)
        session = session_for(quoted_at)
        spot = float(self._ticker.history(period="1d", interval="1m")["Close"].iloc[-1])
        lo, hi = spot * (1 - moneyness), spot * (1 + moneyness)

        expiry_dates = [datetime.strptime(e, "%Y-%m-%d").date() for e in self._ticker.options]
        # Live until the 16:00 ET close of the expiry day; after that it has settled.
        upcoming = [e.isoformat() for e in expiry_dates
                    if e > session or (e == session and market_spec.session_close(session) > quoted_at)]
        rows = []
        for expiry in upcoming[:expiries]:
            chain = self._ticker.option_chain(expiry)
            for df in (chain.calls, chain.puts):
                rows += [r for _, r in df.iterrows() if lo <= r["strike"] <= hi]

        parsed = [(parse_occ(r["contractSymbol"]), r) for r in rows]
        weekly = {s.expiry for s, _ in parsed if s.root == "SPXW"}   # prefer PM-settled SPXW, as for CBOE
        parsed = [(s, r) for s, r in parsed if s.root == "SPXW" or s.expiry not in weekly]
        # Outside the session Yahoo reports open interest as 0 everywhere: that means unknown, not zero.
        has_oi = any((r["openInterest"] or 0) > 0 for _, r in parsed if pd.notna(r["openInterest"]))

        quotes = [
            ChainQuote(
                expiry=s.expiry, option_type=s.option_type, strike=s.strike,
                bid=_num(r["bid"]), ask=_num(r["ask"]), last=_num(r["lastPrice"]),
                volume=int(r["volume"]) if pd.notna(r["volume"]) else None,
                open_interest=int(r["openInterest"]) if has_oi and pd.notna(r["openInterest"]) else None,
                vendor_iv=_num(r["impliedVolatility"]),
            )
            for s, r in parsed
        ]
        quotes.sort(key=lambda q: (q.expiry, q.strike, q.option_type))
        return ChainSnapshot("SPX", self.name, self.delay_minutes, quoted_at, session, spot, quotes)
