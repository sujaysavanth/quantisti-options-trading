"""The paper account's rules: capital each trade holds, when it settles, and at what prices.

Capital held against the starting balance (STARTING_BALANCE):
    defined risk      the most the trade can lose at expiry (a debit's cost; a credit spread's width less the credit)
    unlimited risk    short contracts not covered by a long of the same type use the CBOE rule for uncovered
                      broad-based index options (Rule 12.3): premium + the larger of
                          15% of the index value - the out-of-the-money amount, and
                          10% of the index value (calls) or of the strike (puts),
                      x100 per contract, less the premium received (which is credited). The covered remainder holds
                      its own max loss. Recomputed at the current spot for open trades, as a broker's would be.
    available         starting balance + realised P&L - capital held by open trades. An order needing more is refused.

Settlement: a trade still open on its (earliest) expiry day closes SETTLE_BEFORE the close (15:30 ET, or 12:30 on
an early-close day) at the quote's mids; the quotes are ~15 minutes delayed, so those are ~15:15 prices. A trade
found open after its expiry's close (the service was down) settles at intrinsic value against that day's official
close instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, List, Optional, Sequence

from .. import market_spec

STARTING_BALANCE = 30_000.0
MULTIPLIER = 100
SETTLE_BEFORE = timedelta(minutes=30)
NAKED_PCT, MIN_PCT = 0.15, 0.10


@dataclass
class Position:
    """One leg as the rules see it."""
    strike: float
    option_type: str          # CALL | PUT
    side: str                 # BUY | SELL
    quantity: int
    price: float              # entry price
    mark: Optional[float] = None   # current mid, if known: uncovered shorts' margin follows the market


def sign(p: Position) -> int:
    return 1 if p.side == "BUY" else -1


def intrinsic(option_type: str, strike: float, spot: float) -> float:
    return max(spot - strike, 0.0) if option_type == "CALL" else max(strike - spot, 0.0)


def pl_at(positions: Sequence[Position], spot: float) -> float:
    """Dollar P&L at expiry if the index settles at `spot`."""
    return sum(sign(p) * p.quantity * MULTIPLIER * (intrinsic(p.option_type, p.strike, spot) - p.price) for p in positions)


def max_loss(positions: Sequence[Position]) -> Optional[float]:
    """The largest loss at expiry (a positive number), or None when losses are unlimited (net short calls)."""
    if not positions:
        return 0.0
    net_calls = sum(sign(p) * p.quantity for p in positions if p.option_type == "CALL")
    if net_calls < 0:
        return None
    kinks = [0.0, *sorted({p.strike for p in positions}), 3 * max(p.strike for p in positions)]
    return max(0.0, -min(pl_at(positions, s) for s in kinks))


def _split_uncovered(positions: Sequence[Position]):
    """(covered positions, uncovered short positions). Longs cover shorts of the same type, the most dangerous
    first (lowest-strike calls, highest-strike puts), the pairing a broker uses to keep the requirement low;
    shorts left over are uncovered."""
    covered: List[Position] = []
    naked: List[Position] = []
    for kind, danger in (("CALL", lambda p: p.strike), ("PUT", lambda p: -p.strike)):
        legs = [p for p in positions if p.option_type == kind]
        longs = sum(p.quantity for p in legs if p.side == "BUY")
        shorts = sorted((p for p in legs if p.side == "SELL"), key=danger)                 # most dangerous first
        covered += [p for p in legs if p.side == "BUY"]
        for p in shorts:
            take = min(p.quantity, longs)
            longs -= take
            if take:
                covered.append(Position(p.strike, p.option_type, p.side, take, p.price, p.mark))
            if p.quantity - take:
                naked.append(Position(p.strike, p.option_type, p.side, p.quantity - take, p.price, p.mark))
    return covered, naked


def naked_requirement(p: Position, spot: float) -> float:
    """CBOE requirement for uncovered short index options, per the docstring, for all of p's contracts."""
    otm = max(p.strike - spot, 0.0) if p.option_type == "CALL" else max(spot - p.strike, 0.0)
    floor = MIN_PCT * (spot if p.option_type == "CALL" else p.strike)
    value = p.mark if p.mark is not None else p.price
    per_contract = value + max(NAKED_PCT * spot - otm, floor)
    return per_contract * MULTIPLIER * p.quantity


def capital_held(positions: Sequence[Position], spot: float) -> dict:
    """{"amount": dollars held, "basis": "max loss" | "margin"}. Max losses use entry prices (fixed when the trade
    is opened); uncovered shorts use their current value (mark) in the CBOE formula, less the premium received."""
    covered, naked = _split_uncovered(positions)
    if not naked:
        return {"amount": max_loss(positions) or 0.0, "basis": "max loss"}
    amount = (max_loss(covered) or 0.0) + sum(naked_requirement(p, spot) - p.price * MULTIPLIER * p.quantity for p in naked)
    return {"amount": amount, "basis": "margin"}


def settle_time(expiry: date) -> datetime:
    """When a trade expiring on `expiry` is closed: SETTLE_BEFORE that session's close (aware, UTC)."""
    return market_spec.session_close(expiry) - SETTLE_BEFORE


def settlement_mode(expiry: date, now: datetime) -> Optional[str]:
    """None (not yet), "quote" (settle at the quote's mids now), or "close" (missed: intrinsic at the close)."""
    if now < settle_time(expiry):
        return None
    return "quote" if now < market_spec.session_close(expiry) else "close"


def realised(entries: Iterable[float], exits: Iterable[float], positions: Sequence[Position]) -> float:
    return sum(sign(p) * p.quantity * MULTIPLIER * (x - e) for p, e, x in zip(positions, entries, exits))
