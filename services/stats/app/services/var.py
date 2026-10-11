"""1-day value at risk and expected shortfall of the open paper trades, three ways, plus the tests that check them.

Every method produces a distribution of tomorrow's P&L; VaR at confidence c is the loss exceeded with probability
1 - c (reported as a positive dollar amount), ES the average loss at or beyond it. One day passes in every scenario
(so theta is included), and each day's SPX return comes with that day's VIX change as the IV shift, as in the stress
tests (VIX understates short-dated IV moves, so tails for weekly options are, if anything, too thin).

historical            every SPX day in underlying_daily (since 2010), each a full Black-Scholes revaluation.
                      Slow to react: a calm year after 2020 still carries March 2020.
filtered_historical   the same days with each move rescaled from its own day's volatility to today's: return x
                      sigma_now / sigma_t (and the VIX change by the same ratio), sigma_t an EWMA (lambda 0.94,
                      RiskMetrics) known before day t. sigma_now is the ml service's GARCH forecast for the next
                      session when there is one, else the latest EWMA. Hull & White's volatility-updated historical
                      simulation: the standard fix for the method above.
delta_gamma_vega      the book's Greeks applied to joint-normal (return, VIX change) draws with the mean and covariance
                      of the last LOOKBACK sessions: delta dS + 1/2 gamma dS^2 + vega dVIX + theta. Fast and
                      transparent, but thin-tailed and blind to large moves where the Taylor expansion breaks.

Backtests (Basel-style): a breach is a day whose realised loss exceeded that day's VaR. Kupiec's proportion-of-
failures test asks whether breaches happen at the rate 1 - c; Christoffersen's test whether they cluster. Both are
likelihood ratios against chi-square(1). With 1% expected breaches, about 250 days are needed before either says much.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

CONFIDENCES = (0.95, 0.99)
EWMA_LAMBDA = 0.94
EWMA_WARMUP = 20
LOOKBACK = 504                 # sessions (~2 years) for the delta-gamma-vega covariance
DRAWS = 20_000
SEED = 7

Move = Tuple[float, float]     # (SPX return, VIX change in points)


def var_es(pnl: Sequence[float], confidence: float) -> Tuple[float, float]:
    """(VaR, ES) as positive losses from a sample of P&L."""
    losses = -np.asarray(pnl, dtype=float)
    var = float(np.quantile(losses, confidence))
    tail = losses[losses >= var]
    return var, float(tail.mean()) if tail.size else var


def ewma_sigmas(returns: Sequence[float], lam: float = EWMA_LAMBDA) -> np.ndarray:
    """sigma[t] = EWMA volatility known before return t (seeded with the first EWMA_WARMUP returns' variance);
    sigma[len] = the latest, after the last return."""
    r = np.asarray(returns, dtype=float)
    var = float(np.mean(r[:EWMA_WARMUP] ** 2)) if r.size else 0.0
    out = np.empty(r.size + 1)
    for t, x in enumerate(r):
        out[t] = math.sqrt(var)
        var = lam * var + (1 - lam) * x * x
    out[r.size] = math.sqrt(var)
    return out


def filtered_moves(moves: Sequence[Move], sigma_now: Optional[float]) -> Tuple[List[Move], float, str]:
    """(rescaled moves, sigma used, its source). The warm-up days are dropped."""
    r = [m[0] for m in moves]
    sig = ewma_sigmas(r)
    source = "garch"
    if sigma_now is None:
        sigma_now, source = float(sig[-1]), "ewma"
    out = [(rt * sigma_now / sig[t], dv * sigma_now / sig[t])
           for t, (rt, dv) in enumerate(moves) if t >= EWMA_WARMUP and sig[t] > 0]
    return out, sigma_now, source


def taylor_pnl(totals: Mapping[str, float], spot: float, moves: Sequence[Move], draws: int = DRAWS,
               seed: int = SEED) -> np.ndarray:
    """Delta-gamma-vega-theta P&L over joint-normal draws fitted to `moves`. `totals` are the book's dollar Greeks
    (delta and gamma per SPX point, vega per vol point, theta per day)."""
    m = np.asarray(moves, dtype=float)
    mean, cov = m.mean(axis=0), np.cov(m.T)
    x = np.random.default_rng(seed).multivariate_normal(mean, cov, size=draws)
    ds = spot * x[:, 0]
    return totals["delta"] * ds + 0.5 * totals["gamma"] * ds ** 2 + totals["vega"] * x[:, 1] + totals["theta"]


def summarise(pnl: Sequence[float], details: Dict[str, Any]) -> Dict[str, Any]:
    levels = {f"{c:.2f}": dict(zip(("var", "es"), var_es(pnl, c))) for c in CONFIDENCES} if len(pnl) else {}
    return {"levels": levels, "scenarios": len(pnl), **details}


# --- backtests ------------------------------------------------------------------------------------------------

def _xlogy(x: float, y: float) -> float:
    return 0.0 if x == 0 else x * math.log(y)


def _chi2_1_sf(stat: float) -> float:
    """P(chi-square with 1 dof > stat)."""
    return math.erfc(math.sqrt(max(stat, 0.0) / 2))


def kupiec(breaches: Sequence[bool], confidence: float) -> Dict[str, Any]:
    n, x = len(breaches), int(sum(breaches))
    p = 1 - confidence
    if n == 0:
        return {"observations": 0, "breaches": 0, "expected": 0.0, "lr": None, "p_value": None}
    rate = x / n
    lr = -2 * (_xlogy(n - x, 1 - p) + _xlogy(x, p) - _xlogy(n - x, 1 - rate) - _xlogy(x, rate))
    return {"observations": n, "breaches": x, "expected": n * p, "breach_rate": rate, "lr": lr,
            "p_value": _chi2_1_sf(lr)}


def christoffersen(breaches: Sequence[bool]) -> Dict[str, Any]:
    """Independence: is a breach more likely the day after a breach?"""
    b = [bool(v) for v in breaches]
    pairs = list(zip(b, b[1:]))
    n00 = sum(1 for a, c in pairs if not a and not c)
    n01 = sum(1 for a, c in pairs if not a and c)
    n10 = sum(1 for a, c in pairs if a and not c)
    n11 = sum(1 for a, c in pairs if a and c)
    if not pairs or n01 + n11 == 0:
        return {"transitions": len(pairs), "lr": None, "p_value": None}
    pi0 = n01 / (n00 + n01) if n00 + n01 else 0.0
    pi1 = n11 / (n10 + n11) if n10 + n11 else 0.0
    pi = (n01 + n11) / len(pairs)
    restricted = _xlogy(n00 + n10, 1 - pi) + _xlogy(n01 + n11, pi)
    free = _xlogy(n00, 1 - pi0) + _xlogy(n01, pi0) + _xlogy(n10, 1 - pi1) + _xlogy(n11, pi1)
    lr = -2 * (restricted - free)
    return {"transitions": len(pairs), "after_no_breach": pi0, "after_breach": pi1, "lr": lr,
            "p_value": _chi2_1_sf(lr)}


def backtest(rows: Sequence[Mapping[str, Any]], realised: Mapping[Any, float]) -> Dict[str, Any]:
    """`rows`: stored VaR ({session, method, confidence, var}); `realised`: session -> next session's P&L.
    Per method and confidence: the days with an outcome, breaches, Kupiec and Christoffersen."""
    groups: Dict[Tuple[str, float], List[Mapping[str, Any]]] = {}
    for r in rows:
        groups.setdefault((r["method"], float(r["confidence"])), []).append(r)
    out = []
    for (method, c), rs in sorted(groups.items()):
        known = [r for r in sorted(rs, key=lambda r: r["session"]) if r["session"] in realised]
        breaches = [-realised[r["session"]] > float(r["var"]) for r in known]
        out.append({"method": method, "confidence": c, "kupiec": kupiec(breaches, c),
                    "christoffersen": christoffersen(breaches),
                    "breach_days": [str(r["session"]) for r, hit in zip(known, breaches) if hit]})
    return {"tests": out}
