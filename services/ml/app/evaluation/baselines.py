"""Baseline forecasts of next week's close return, as quantiles.

Every baseline forecasts one number per week, the weekly volatility sigma, and turns it into quantiles
the same way: q = sigma * z_q, where z_q are the empirical quantiles of (return / sigma) over the
training years. That mapping absorbs drift, fat tails and skew (SPX falls further than it rises) and any
constant bias in sigma, so the baselines differ only in how well they track volatility. The exception is
`vix_raw`: VIX as published, normal quantiles, zero mean; the market's own number, no fitting at all.

    vix_raw     sigma = VIX/100 * sqrt(sessions/252), normal quantiles
    vix_scaled  the same sigma, empirical z (one multiplier per quantile, learned on training years)
    rv_20d      20-day realised volatility: "next week looks like the last month"
    har_rv      HAR-RV (Corsi 2009): next week's variance regressed on last day / week / month of
                squared daily returns; the standard benchmark for volatility forecasting
    garch       GARCH(1,1) on daily returns (the `arch` package), summed over next week's sessions
    straddle    the ATM straddle for next week's expiry at the anchor's close (real chains: OptionsDX 2010-2023, CBOE from Oct 2026)

`fit` sees training weeks only; `predict` sees test weeks' features, never their labels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import NormalDist
from typing import Dict, List

import numpy as np
import pandas as pd

from ..dataset.options import preferred_source, straddle_sigma_week
from .metrics import QUANTILES

TRADING_DAYS = 252
NORMAL_Z = np.array([NormalDist().inv_cdf(t) for t in QUANTILES])


@dataclass
class Context:
    """Data the baselines need beyond the weekly rows."""
    daily: pd.DataFrame                                   # date, close (every session, oldest first)
    straddle_sigma: Dict = field(default_factory=dict)    # anchor_date -> weekly sigma implied by the ATM straddle

    def __post_init__(self):
        d = self.daily.sort_values("date")
        self.dates = pd.to_datetime(d["date"]).to_numpy()
        self.returns = np.log(d["close"].astype(float)).diff().to_numpy()      # r[i]: close[i-1] -> close[i]
        r2 = pd.Series(self.returns ** 2)
        self.r2_day, self.r2_week, self.r2_month = r2.to_numpy(), r2.rolling(5).mean().to_numpy(), r2.rolling(22).mean().to_numpy()

    def index_of(self, days) -> np.ndarray:
        """Position of each date in the daily series (dates must be sessions in it)."""
        return np.searchsorted(self.dates, pd.to_datetime(list(days)).to_numpy())


def week_sigma(daily_variance: np.ndarray, sessions: np.ndarray) -> np.ndarray:
    return np.sqrt(np.clip(daily_variance, 1e-10, None) * sessions)


class SigmaBaseline:
    """sigma per week -> quantiles via empirical z from the training weeks."""
    name = "base"

    def fit_sigma(self, train: pd.DataFrame, ctx: Context) -> None:
        pass

    def sigma(self, rows: pd.DataFrame, ctx: Context) -> np.ndarray:
        raise NotImplementedError

    def fit(self, train: pd.DataFrame, ctx: Context) -> None:
        self.fit_sigma(train, ctx)
        s = self.sigma(train, ctx)
        ok = np.isfinite(s) & (s > 0)
        if ok.sum() < 20:
            raise ValueError(f"{self.name}: only {ok.sum()} training weeks with a sigma")
        self.z = np.quantile(train["close_ret"].to_numpy()[ok] / s[ok], QUANTILES)

    def predict(self, test: pd.DataFrame, ctx: Context) -> np.ndarray:
        return self.sigma(test, ctx)[:, None] * self.z[None, :]


class VixScaled(SigmaBaseline):
    name = "vix_scaled"

    def sigma(self, rows, ctx):
        return rows["vix_close"].to_numpy() / 100 * np.sqrt(rows["sessions_next"].to_numpy() / TRADING_DAYS)


class VixRaw(VixScaled):
    name = "vix_raw"

    def fit(self, train, ctx):
        self.z = NORMAL_Z


class RealisedVol(SigmaBaseline):
    name = "rv_20d"

    def sigma(self, rows, ctx):
        return rows["rv_20d"].to_numpy() * np.sqrt(rows["sessions_next"].to_numpy() / TRADING_DAYS)


class HarRv(SigmaBaseline):
    """Next week's average daily r^2 = b0 + b_d * r^2(day) + b_w * mean r^2(5 days) + b_m * mean r^2(22 days)."""
    name = "har_rv"

    @staticmethod
    def _x(rows, ctx) -> np.ndarray:
        i = ctx.index_of(rows["anchor_date"])
        return np.column_stack([np.ones(len(i)), ctx.r2_day[i], ctx.r2_week[i], ctx.r2_month[i]])

    @staticmethod
    def _target(rows, ctx) -> np.ndarray:
        start, end = ctx.index_of(rows["anchor_date"]) + 1, ctx.index_of(rows["next_anchor_date"]) + 1
        return np.array([ctx.r2_day[s:e].mean() for s, e in zip(start, end)])

    def fit_sigma(self, train, ctx):
        x, y = self._x(train, ctx), self._target(train, ctx)
        ok = np.isfinite(x).all(axis=1) & np.isfinite(y)
        self.beta, *_ = np.linalg.lstsq(x[ok], y[ok], rcond=None)

    def sigma(self, rows, ctx):
        return week_sigma(self._x(rows, ctx) @ self.beta, rows["sessions_next"].to_numpy())


class Garch(SigmaBaseline):
    """GARCH(1,1), fitted on daily returns up to the end of the training weeks, then run forward with
    fixed parameters: the variance forecast at each anchor uses returns up to that close only."""
    name = "garch"

    def fit_sigma(self, train, ctx):
        from arch import arch_model
        cutoff = ctx.index_of([train["next_anchor_date"].max()])[0]
        r = ctx.returns[1:cutoff + 1] * 100                                   # percent, as arch prefers
        res = arch_model(r, mean="Constant", vol="GARCH", p=1, q=1, dist="normal", rescale=False).fit(disp="off")
        self.mu, self.omega, self.alpha, self.beta_ = (float(res.params[k]) for k in ("mu", "omega", "alpha[1]", "beta[1]"))
        self.h_next = self._filter(ctx.returns * 100)                        # h_next[i]: variance of day i+1, known at close i

    def _filter(self, r: np.ndarray) -> np.ndarray:
        e = np.nan_to_num(r - self.mu)
        h = np.empty(len(r))
        h_prev = np.nanvar(r)
        for i in range(len(r)):
            h_prev = self.omega + self.alpha * e[i] ** 2 + self.beta_ * h_prev
            h[i] = h_prev
        return h

    def sigma(self, rows, ctx):
        i = ctx.index_of(rows["anchor_date"])
        n = rows["sessions_next"].to_numpy()
        persistence = self.alpha + self.beta_
        h1 = self.h_next[i]
        if persistence >= 0.9999:
            total = h1 * n
        else:
            long_run = self.omega / (1 - persistence)
            # sum over h = 1..n of long_run + persistence^(h-1) * (h1 - long_run)
            total = n * long_run + (h1 - long_run) * (1 - persistence ** n) / (1 - persistence)
        return np.sqrt(np.clip(total, 1e-12, None)) / 100


class Straddle(SigmaBaseline):
    """ATM straddle mid / spot ~= sigma * sqrt(2/pi) for a normal move: sigma = straddle / spot / 0.798."""
    name = "straddle"

    def sigma(self, rows, ctx):
        return np.array([ctx.straddle_sigma.get(a, np.nan) for a in rows["anchor_date"]], dtype=float)


def straddle_sigma(chains: pd.DataFrame) -> Dict:
    """chains: one anchor's quotes for next week's expiry per anchor_date (store.load_anchor_chains).
    Weekly sigma from the ATM straddle of each anchor's preferred source (dataset/options.py)."""
    out = {}
    for anchor, g in chains.groupby("anchor_date"):
        sigma = straddle_sigma_week(g[g["source"] == preferred_source(g)])
        if sigma:
            out[anchor] = sigma
    return out


def all_baselines(include_straddle: bool = True) -> List[SigmaBaseline]:
    out: List[SigmaBaseline] = [VixRaw(), VixScaled(), RealisedVol(), HarRv(), Garch()]
    return out + [Straddle()] if include_straddle else out
