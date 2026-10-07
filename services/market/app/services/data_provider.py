"""Data provider service for fetching and generating market data."""

import logging
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional

from psycopg2.extras import RealDictCursor

from .. import market_spec
from ..config import get_settings
from ..db.connection import get_db_connection, return_db_connection
from ..models.market_data import CandleData
from .chains import Quote, build_snapshot_chain, build_synthetic_chain, preferred_snapshot_source
from .live import Spot, default_session, pick_spot, snapshot_as_of

logger = logging.getLogger(__name__)

DEFAULT_VIX = 18.0  # long-run average, used only if no VIX row exists for a date


class DataProvider:
    """Provider for underlying data and option chains."""

    def __init__(self):
        self.settings = get_settings()
        self.symbol = market_spec.SYMBOL

    @contextmanager
    def _cursor(self) -> Iterator[RealDictCursor]:
        conn = get_db_connection()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                yield cur
            finally:
                cur.close()
        finally:
            return_db_connection(conn)

    # ------------------------------------------------------------ underlying

    def get_historical_data(self, start_date: date, end_date: date) -> List[CandleData]:
        """Daily candles for the underlying between two dates, inclusive."""
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT date, open, high, low, close, volume, historical_volatility
                FROM underlying_daily
                WHERE symbol = %s AND date >= %s AND date <= %s
                ORDER BY date ASC
                """,
                (self.symbol, start_date, end_date),
            )
            rows = cur.fetchall()

        return [
            CandleData(
                date=row["date"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]),
                historical_volatility=float(row["historical_volatility"]) if row["historical_volatility"] else None,
            )
            for row in rows
        ]

    def get_latest_spot_price(self) -> Optional[Dict[str, Any]]:
        """Latest close, with the change from the previous close."""
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT date, close, volume, historical_volatility
                FROM underlying_daily
                WHERE symbol = %s
                ORDER BY date DESC
                LIMIT 2
                """,
                (self.symbol,),
            )
            rows = cur.fetchall()

        if not rows:
            return None
        latest = rows[0]
        price = float(latest["close"])
        change = price - float(rows[1]["close"]) if len(rows) > 1 else None
        return {
            "date": latest["date"],
            "price": price,
            "volume": int(latest["volume"]),
            "historical_volatility": float(latest["historical_volatility"]) if latest["historical_volatility"] else None,
            "change": change,
            "change_percent": change / (price - change) * 100 if change is not None else None,
        }

    def get_spot_price_for_date(self, target_date: date) -> Optional[float]:
        """Close on `target_date`, or None if it was not a trading day / not loaded."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT close FROM underlying_daily WHERE symbol = %s AND date = %s",
                (self.symbol, target_date),
            )
            row = cur.fetchone()
        return float(row["close"]) if row else None

    # ------------------------------------------------------------ intraday

    @staticmethod
    def _et_day(on: date):
        """[start, end) of an ET calendar day, as aware datetimes (intraday_bars.ts is UTC)."""
        start = datetime.combine(on, time(0), market_spec.TZ)
        return start, start + timedelta(days=1)

    def get_intraday_bars(self, symbol: str, interval: str, on: date) -> List[Dict[str, Any]]:
        start, end = self._et_day(on)
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT ts, open, high, low, close, volume, source
                FROM intraday_bars
                WHERE symbol = %s AND interval = %s AND ts >= %s AND ts < %s
                ORDER BY ts
                """,
                (symbol, interval, start, end),
            )
            return cur.fetchall()

    def latest_intraday_session(self, symbol: str, intervals=("1m", "5m")) -> Optional[date]:
        """ET date of the newest bar of `symbol` at any of `intervals`."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT (max(ts) AT TIME ZONE 'America/New_York')::date AS d FROM intraday_bars"
                " WHERE symbol = %s AND interval = ANY(%s)",
                (symbol, list(intervals)),
            )
            row = cur.fetchone()
        return row["d"] if row else None

    def latest_bar(self, symbol: str, on: date) -> Optional[Dict[str, Any]]:
        """The 1m or 5m bar of `on` that ends last (1m on a tie)."""
        start, end = self._et_day(on)
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT ts, interval, close FROM intraday_bars
                WHERE symbol = %s AND interval IN ('1m', '5m') AND ts >= %s AND ts < %s
                ORDER BY ts + CASE interval WHEN '1m' THEN interval '1 minute' ELSE interval '5 minutes' END DESC,
                         interval
                LIMIT 1
                """,
                (symbol, start, end),
            )
            return cur.fetchone()

    def resolve_spot(self, on: date) -> Optional[Spot]:
        """The day's close, or while the session runs (no close stored yet) its latest SPX bar."""
        close = self.get_spot_price_for_date(on)
        return pick_spot(on, close, None if close is not None else self.latest_bar(self.symbol, on))

    # ------------------------------------------------------------ pricing inputs

    def get_rate(self, on: date) -> float:
        """Most recent T-bill rate on or before `on` (FRED publishes with a lag)."""
        with self._cursor() as cur:
            cur.execute("SELECT rate FROM rates_daily WHERE date <= %s ORDER BY date DESC LIMIT 1", (on,))
            row = cur.fetchone()
        return float(row["rate"]) if row else market_spec.FALLBACK_RATE

    def get_vix(self, on: date) -> float:
        """VIX close on `on`; while that session runs, its latest VIX bar; else the last close before it."""
        with self._cursor() as cur:
            cur.execute("SELECT date, close FROM vix_daily WHERE date <= %s ORDER BY date DESC LIMIT 1", (on,))
            row = cur.fetchone()
        if row is None or row["date"] != on:
            bar = self.latest_bar("VIX", on)
            if bar is not None:
                return float(bar["close"])
        if not row:
            logger.warning("No VIX data on or before %s; using %.1f", on, DEFAULT_VIX)
            return DEFAULT_VIX
        return float(row["close"])

    def get_vix_history(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT date, close FROM vix_daily WHERE date >= %s AND date <= %s ORDER BY date",
                (start_date, end_date),
            )
            return [{"date": r["date"], "close": float(r["close"])} for r in cur.fetchall()]

    def get_snapshot_quotes(self, on: date, expiry: date) -> List[Dict[str, Any]]:
        """Quotes from one source only: mixing CBOE and Yahoo rows would list every strike twice."""
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT source FROM option_chain_snapshots
                WHERE symbol = %s AND snapshot_date = %s AND expiry_date = %s
                """,
                (self.symbol, on, expiry),
            )
            source = preferred_snapshot_source(r["source"] for r in cur.fetchall())
            if source is None:
                return []
            cur.execute(
                """
                SELECT strike, option_type, bid, ask, last, open_interest, volume, underlying_price, quoted_at
                FROM option_chain_snapshots
                WHERE symbol = %s AND snapshot_date = %s AND expiry_date = %s AND source = %s
                """,
                (self.symbol, on, expiry, source),
            )
            return cur.fetchall()

    # ------------------------------------------------------------ option chain

    def default_expiry(self, target_date: date, now: Optional[datetime] = None) -> date:
        """Nearest expiry that still has time left at the chain's valuation time."""
        as_of = market_spec.valuation_time(target_date, now)
        expiry = market_spec.next_expiry(target_date)
        if market_spec.year_fraction(as_of, expiry) > 0:
            return expiry
        return market_spec.next_expiry(target_date, min_dte=1)

    def generate_option_chain(
        self,
        target_date: Optional[date] = None,
        expiry_date: Optional[date] = None,
        strike_range: int = 10,
        now: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """Option chain for `target_date` (default: the latest session, today once intraday bars arrive).

        Uses a collected snapshot of listed quotes when one exists for that day
        and expiry; otherwise prices the chain with Black-Scholes from the spot
        (the close, or the latest bar while the session runs), VIX and the T-bill rate.
        """
        if target_date is None:
            latest = self.get_latest_spot_price()
            target_date = default_session(latest["date"] if latest else None, self.latest_intraday_session(self.symbol))
            if target_date is None:
                return None
        spot_quote = self.resolve_spot(target_date)
        if spot_quote is None:
            return None
        spot = spot_quote.price

        if expiry_date is None:
            expiry_date = self.default_expiry(target_date, now)
        elif not market_spec.is_expiry(expiry_date):
            raise ValueError(f"{expiry_date} is not a listed {self.symbol} expiry")

        valuation = market_spec.valuation_time(target_date, now or datetime.now(timezone.utc))
        T = market_spec.year_fraction(valuation, expiry_date)
        if T <= 0:
            logger.warning("Expiry %s has no time left as of %s", expiry_date, valuation)
            return None

        rate = self.get_rate(target_date)
        live = {"spot_source": spot_quote.source}

        rows = self.get_snapshot_quotes(target_date, expiry_date)
        if rows:
            as_of = snapshot_as_of(valuation, max((r["quoted_at"] for r in rows if r["quoted_at"]), default=None))
            quotes = [
                Quote(
                    strike=float(r["strike"]),
                    option_type=r["option_type"],
                    bid=float(r["bid"]) if r["bid"] is not None else None,
                    ask=float(r["ask"]) if r["ask"] is not None else None,
                    last=float(r["last"]) if r["last"] is not None else None,
                    open_interest=r["open_interest"],
                    volume=r["volume"],
                )
                for r in rows
            ]
            chain = build_snapshot_chain(quotes, spot, target_date, expiry_date,
                                         market_spec.year_fraction(as_of, expiry_date), rate, strike_range)
            if chain:
                return {**chain, **live, "as_of": as_of}
            logger.warning("Snapshot for %s/%s unusable; falling back to synthetic", target_date, expiry_date)

        chain = build_synthetic_chain(spot, target_date, expiry_date, T, rate, self.get_vix(target_date), strike_range)
        return {**chain, **live, "as_of": valuation}
