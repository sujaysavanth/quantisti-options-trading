"""What the bridge remembers between messages, and the market-stream quote built from it.

The bridge keeps only the latest of everything:
- SPX spot: the newest 1m bar on market.bars.1m
- the chain: the newest message per expiry on options.chain.quotes
- the risk-free rate: the newest T-bill row on market.daily

`to_quote()` turns that into the payload market-stream's POST /v1/quotes takes:
legs for every live expiry, a per-expiry summary, and a `default_expiry` (the
nearest one at least `min_dte` calendar days out, the same rule backtests use)
that the UI selects when the user hasn't picked one.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .. import market_spec
from ..producers.envelope import BarPayload, ChainPayload, DailyPayload, Envelope
from .pricing import bs_delta, implied_vol, infer_forward


@dataclass
class Chain:
    payload: ChainPayload
    source: str
    delay_minutes: int


def occ_symbol(expiry: date, option_type: str, strike: float, root: str = "SPXW") -> str:
    """SPXW + YYMMDD + C/P + strike x 1000 (8 digits): the id market-stream and paper trades use."""
    return f"{root}{expiry:%y%m%d}{option_type}{round(strike * 1000):08d}"


def _mid(bid: Optional[float], ask: Optional[float]) -> Optional[float]:
    if bid and ask and ask >= bid > 0:
        return (bid + ask) / 2
    return None


class BridgeState:
    def __init__(self, min_dte: int = 1):
        self.min_dte = min_dte
        self.spot: Optional[BarPayload] = None
        self.rate: Optional[DailyPayload] = None
        self.chains: Dict[date, Chain] = {}

    def apply(self, env: Envelope) -> bool:
        """Take in one message; True if it changed what we would publish."""
        p = env.payload
        if isinstance(p, BarPayload):
            if p.symbol == "SPX" and (self.spot is None or p.ts > self.spot.ts):
                self.spot = p
                return True
        elif isinstance(p, ChainPayload):
            old = self.chains.get(p.expiry)
            if old is None or p.quoted_at >= old.payload.quoted_at:
                self.chains[p.expiry] = Chain(p, env.source, env.delay_minutes)
                return True
        elif isinstance(p, DailyPayload):
            if p.dataset == "rates" and (self.rate is None or p.date > self.rate.date):
                self.rate = p
                return True
        return False

    def pick_expiry(self, now: datetime) -> Optional[date]:
        # Forget expiries that have settled (their 16:00 ET close has passed).
        for expiry in [e for e in self.chains if market_spec.session_close(e) <= now]:
            del self.chains[expiry]
        if not self.chains:
            return None
        today = now.astimezone(market_spec.TZ).date()
        far_enough = [e for e in self.chains if e >= today + timedelta(days=self.min_dte)]
        return min(far_enough) if far_enough else min(self.chains)

    def _expiry_legs(self, chain: Chain, rate: float, spot_hint: float, today: date) -> Tuple[List[dict], dict]:
        """Legs for one expiry, priced against that expiry's own parity forward, plus its summary row."""
        c, expiry, q = chain.payload, chain.payload.expiry, market_spec.DIVIDEND_YIELD
        T = market_spec.year_fraction(c.quoted_at, expiry)
        mids = [(qt.strike, qt.option_type, m) for qt in c.quotes if (m := _mid(qt.bid, qt.ask)) is not None]
        forward = infer_forward(mids, T, rate, spot_hint=c.underlying_price or spot_hint)
        # Spot consistent with this expiry's option quotes.
        implied_spot = forward * math.exp(-(rate - q) * T) if forward else spot_hint

        legs, atm_ivs = [], []
        for qt in c.quotes:
            iv = implied_vol(_mid(qt.bid, qt.ask), implied_spot, qt.strike, T, rate, q, qt.option_type)
            if iv is not None and abs(qt.strike - implied_spot) <= 2 * market_spec.STRIKE_STEP:
                atm_ivs.append(iv)
            legs.append({
                "identifier": occ_symbol(expiry, qt.option_type, qt.strike),
                "strike": qt.strike,
                "option_type": "CALL" if qt.option_type == "C" else "PUT",
                "expiry": expiry.isoformat(),
                "bid": qt.bid, "ask": qt.ask, "last": qt.last,
                "volume": qt.volume, "open_interest": qt.open_interest,
                "iv": round(iv, 4) if iv is not None else None,
                "delta": round(bs_delta(implied_spot, qt.strike, T, rate, iv, q, qt.option_type), 4) if iv is not None else None,
            })
        summary = {
            "expiry": expiry.isoformat(),
            "dte": (expiry - today).days,
            "atm_iv": round(statistics.median(atm_ivs), 4) if atm_ivs else None,
            "forward": round(forward, 2) if forward else None,
            "quoted_at": c.quoted_at.isoformat(),
        }
        return legs, summary

    def to_quote(self, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        now = now or datetime.now(timezone.utc)
        default = self.pick_expiry(now)          # also forgets settled expiries
        if default is None:
            return None
        main = self.chains[default]
        c = main.payload
        rate = self.rate.rate if self.rate else market_spec.FALLBACK_RATE

        # Last price: the newest of the SPX bar and the chain's own underlying price.
        if self.spot and (c.underlying_price is None or self.spot.ts >= c.quoted_at):
            last_price, price_time = self.spot.close, self.spot.ts
        else:
            last_price, price_time = c.underlying_price, c.quoted_at
        if last_price is None:
            return None

        today = now.astimezone(market_spec.TZ).date()
        legs, expiries = [], []
        for expiry in sorted(self.chains):
            expiry_legs, summary = self._expiry_legs(self.chains[expiry], rate, last_price, today)
            legs += expiry_legs
            expiries.append(summary)
        default_summary = next(e for e in expiries if e["expiry"] == default.isoformat())

        return {
            "symbol": c.symbol,
            "last_price": round(last_price, 2),
            "timestamp": price_time.isoformat(),
            "spot_iv": default_summary["atm_iv"],
            "legs": legs,
            "expiries": expiries,
            "default_expiry": default.isoformat(),
            "source": main.source,
            "delay_minutes": main.delay_minutes,
            "quoted_at": c.quoted_at.isoformat(),
        }
