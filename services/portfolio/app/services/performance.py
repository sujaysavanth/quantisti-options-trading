"""Performance of the paper account: pure functions over close snapshots, closed trades and SPX / rate history.

Equity (from close snapshots, one per session):
    daily returns     account value close-to-close; a session with no snapshot makes the next return span the gap
                      (counted in `missing_sessions`)
    total return      last account value / starting balance - 1 (since the account opened, including P&L from
                      before snapshots began); period return = last / first snapshot in the range - 1
    volatility        stdev of daily returns x sqrt(252)
    Sharpe / Sortino  same definitions as the backtest metrics (metrics_calculator.py), on daily excess returns
                      over that day's 3-month T-bill (rates_daily, FRED DGS3MO) / 252, annualised by sqrt(252);
                      Sortino's downside deviation is below the risk-free rate
    max drawdown      deepest fall from a running peak (the starting balance counts as the first peak), with the
                      sessions from that peak to the trough and to recovery (None while still under water)
    vs SPX            buy-and-hold SPX over the same sessions (underlying_daily closes); beta and correlation of
                      daily returns
Trades (closed only): win rate, average win / loss, profit factor (gross wins / gross losses), expectancy (mean
P&L per trade), largest win / loss, median holding time, and the same per strategy (the trade's nickname).

Small samples: the ratios (volatility, Sharpe, Sortino, beta) need MIN_RETURNS daily returns and are None below
it; trade stats are always computed but flagged until MIN_TRADES trades have closed.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from statistics import median
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from .. import market_spec

PERIODS_PER_YEAR = 252
MIN_RETURNS = 20
MIN_TRADES = 10


def _rate_on(rates: Sequence[Tuple[date, float]], day: date) -> float:
    """Latest rate on or before `day` (FRED lags a day or two); market_spec.FALLBACK_RATE if none."""
    rate = None
    for d, r in rates:
        if d > day:
            break
        rate = r
    return market_spec.FALLBACK_RATE if rate is None else rate


def _ratio(mean: float, dev: float) -> Optional[float]:
    return None if dev == 0 else mean / dev * math.sqrt(PERIODS_PER_YEAR)


def drawdown(values: Sequence[float], sessions: Sequence[date]) -> Dict[str, Any]:
    """Max drawdown of `values` (values[0] is the starting peak, sessions[0] its date or None: a None peak means
    the starting balance)."""
    peak_i, worst, worst_peak, worst_trough = 0, 0.0, 0, 0
    for i, v in enumerate(values):
        if v > values[peak_i]:
            peak_i = i
        dd = v / values[peak_i] - 1
        if dd < worst:
            worst, worst_peak, worst_trough = dd, peak_i, i
    recovered = next((i for i in range(worst_trough, len(values)) if values[i] >= values[worst_peak]), None)
    return {
        "max_drawdown": worst,
        "peak": sessions[worst_peak] if worst < 0 else None,
        "trough": sessions[worst_trough] if worst < 0 else None,
        "sessions_to_trough": worst_trough - worst_peak if worst < 0 else 0,
        "sessions_to_recover": (recovered - worst_trough) if worst < 0 and recovered is not None else None,
        "current_drawdown": values[-1] / max(values) - 1,
    }


def equity_stats(snapshots: Sequence[Mapping[str, Any]], starting_balance: float,
                 rates: Sequence[Tuple[date, float]], spx: Mapping[date, float]) -> Dict[str, Any]:
    """`snapshots`: close snapshots ({session, account_value}) in session order."""
    points = [(s["session"], float(s["account_value"])) for s in snapshots]
    out: Dict[str, Any] = {"sessions": len(points), "first_session": None, "last_session": None,
                           "returns": 0, "missing_sessions": 0, "total_return": None, "period_return": None, "volatility": None,
                           "sharpe": None, "sortino": None, "drawdown": None, "spx_return": None, "beta": None,
                           "correlation": None}
    if not points:
        return out
    days = [d for d, _ in points]
    values = [v for _, v in points]
    expected = market_spec.trading_days(days[0], days[-1])
    out.update(first_session=days[0], last_session=days[-1], returns=len(values) - 1,
               missing_sessions=len(expected) - len(days),
               total_return=values[-1] / starting_balance - 1, period_return=values[-1] / values[0] - 1,
               drawdown=drawdown([starting_balance, *values], [None, *days]))

    if days[0] in spx and days[-1] in spx:
        out["spx_return"] = spx[days[-1]] / spx[days[0]] - 1

    r = np.array([values[i] / values[i - 1] - 1 for i in range(1, len(values))])
    if len(r) < MIN_RETURNS:
        return out
    rf = np.array([_rate_on(rates, days[i - 1]) / PERIODS_PER_YEAR for i in range(1, len(days))])
    excess = r - rf
    out["volatility"] = float(np.std(r, ddof=1)) * math.sqrt(PERIODS_PER_YEAR)
    out["sharpe"] = _ratio(float(np.mean(excess)), float(np.std(excess, ddof=1)))
    out["sortino"] = _ratio(float(np.mean(excess)), float(np.sqrt(np.mean(np.minimum(excess, 0.0) ** 2))))

    pairs = [(r[i - 1], spx[days[i]] / spx[days[i - 1]] - 1) for i in range(1, len(days))
             if days[i] in spx and days[i - 1] in spx]
    if len(pairs) >= MIN_RETURNS:
        p, m = np.array(pairs).T
        if np.var(m, ddof=1) > 0:
            out["beta"] = float(np.cov(p, m, ddof=1)[0, 1] / np.var(m, ddof=1))
            if np.std(p) > 0:
                out["correlation"] = float(np.corrcoef(p, m)[0, 1])
    return out


def _parse(ts: Any) -> datetime:
    return ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts).replace("Z", "+00:00"))


def _trade_block(trades: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    pnl = [float(t["pnl"]) for t in trades]
    wins = [p for p in pnl if p > 0]
    losses = [p for p in pnl if p < 0]
    hours = [(_parse(t["closed_at"]) - _parse(t["created_at"])).total_seconds() / 3600
             for t in trades if t.get("closed_at")]
    return {
        "trades": len(pnl),
        "total_pnl": sum(pnl),
        "win_rate": len(wins) / len(pnl) if pnl else None,
        "average_win": sum(wins) / len(wins) if wins else None,
        "average_loss": sum(losses) / len(losses) if losses else None,
        "profit_factor": sum(wins) / -sum(losses) if losses else None,
        "expectancy": sum(pnl) / len(pnl) if pnl else None,
        "largest_win": max(wins) if wins else None,
        "largest_loss": min(losses) if losses else None,
        "median_holding_hours": median(hours) if hours else None,
    }


def trade_stats(trades: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    closed = [t for t in trades if t["status"] == "closed"]
    groups: Dict[str, List[Mapping[str, Any]]] = {}
    for t in closed:
        groups.setdefault(t.get("nickname") or "Unnamed", []).append(t)
    return {**_trade_block(closed),
            "by_strategy": {name: _trade_block(g) for name, g in sorted(groups.items())}}


def performance(snapshots: Sequence[Mapping[str, Any]], trades: Sequence[Mapping[str, Any]], starting_balance: float,
                rates: Sequence[Tuple[date, float]], spx: Mapping[date, float]) -> Dict[str, Any]:
    equity = equity_stats(snapshots, starting_balance, rates, spx)
    trade = trade_stats(trades)
    notes = []
    if equity["returns"] < MIN_RETURNS:
        notes.append(f"{equity['returns']} daily returns so far: volatility, Sharpe, Sortino and beta need "
                     f"{MIN_RETURNS}.")
    if trade["trades"] < MIN_TRADES:
        notes.append(f"{trade['trades']} closed trades: trade statistics aren't meaningful below {MIN_TRADES}.")
    if equity["missing_sessions"]:
        notes.append(f"{equity['missing_sessions']} sessions have no close snapshot; returns span those gaps.")
    return {"starting_balance": starting_balance, "equity": equity, "trades": trade,
            "meaningful": equity["returns"] >= MIN_RETURNS and trade["trades"] >= MIN_TRADES,
            "notes": notes}
