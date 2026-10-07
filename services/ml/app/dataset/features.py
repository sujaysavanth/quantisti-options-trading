"""Weekly features, computed as of each anchor's close (point in time).

`build_features` is pure and vectorised: daily SPX/VIX/rate frames in, one row per anchor out. The
same function builds the training history and the latest week for serving, so the two can't drift.

Nothing here may look past the anchor: rolling windows end at the anchor's close, EMAs only run
forward, and as-of lookups take the last value on or before the anchor (strictly before, for the
T-bill rate, which FRED publishes a day late). `tests/test_dataset.py` checks this by rebuilding
from data cut off at an anchor and comparing.

Two groups of columns:
- legacy: the columns `weekly_features` always had, with their original definitions (simple-mean
  RSI, population-std volatility in percent, EMA MACD, ATR in index points), now computed over the
  right window. `weekly_change_pct` and `weekly_high_low_range_pct` used to span the whole 60-day
  fetch; they now cover the week.
- MODEL_FEATURES: what the forecast models use. Scale-free (returns, ratios, vol) so 2010 at SPX 1,100
  and 2026 at SPX 7,800 are comparable.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import pandas as pd

from .weeks import monday_of, sessions_next_week

FEATURE_VERSION = 1
TRADING_DAYS = 252

MODEL_FEATURES = (
    "ret_1w", "ret_4w", "range_1w",                     # this week and the last month
    "rv_5d", "rv_20d", "rv_60d",                        # realised vol, annualised, decimal
    "vix_close", "vix_change_1w", "vix_hv_spread", "vix_pct_1y",
    "rsi_14", "bb_width", "atr_pct", "dist_ma50", "drawdown_52w", "volume_ratio",
    "rate_3m", "sessions_next",
)
LEGACY_ONLY = ("weekly_change_pct", "weekly_high_low_range_pct", "macd", "macd_signal",
               "historical_vol_10d", "historical_vol_20d", "atr_14")
COLUMNS = ("week_start_date", "anchor_date", *LEGACY_ONLY, *MODEL_FEATURES)


def _series(df: pd.DataFrame, column: str) -> pd.Series:
    s = pd.Series(df[column].astype(float).to_numpy(), index=pd.to_datetime(df["date"]))
    return s.sort_index()


def _asof(s: pd.Series, at: pd.DatetimeIndex, strict: bool = False) -> np.ndarray:
    """Last value of `s` on (or, if strict, before) each time in `at`; NaN when there is none."""
    pos = s.index.searchsorted(at, side="left" if strict else "right") - 1
    values = s.to_numpy()
    return np.where(pos >= 0, values[np.clip(pos, 0, None)], np.nan)


def daily_indicators(daily: pd.DataFrame) -> pd.DataFrame:
    """Per-session indicators; each value uses that session and earlier ones only."""
    c, h, lo, v = (_series(daily, k) for k in ("close", "high", "low", "volume"))
    logret = np.log(c).diff()
    prev_close = c.shift(1)
    true_range = pd.concat([h - lo, (h - prev_close).abs(), (lo - prev_close).abs()], axis=1).max(axis=1)
    true_range.iloc[0] = np.nan                                  # no previous close on the first day
    delta = c.diff()
    gain, loss = delta.clip(lower=0).rolling(14).mean(), (-delta.clip(upper=0)).rolling(14).mean()
    ema_fast, ema_slow = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    macd = ema_fast - ema_slow
    sma20, sd20 = c.rolling(20).mean(), c.rolling(20).std()
    atr14 = true_range.rolling(14).mean()
    annualise = math.sqrt(TRADING_DAYS)
    return pd.DataFrame({
        "close": c,
        "rv_5d": logret.rolling(5).std() * annualise,
        "rv_20d": logret.rolling(20).std() * annualise,
        "rv_60d": logret.rolling(60).std() * annualise,
        "historical_vol_10d": logret.rolling(10).std(ddof=0) * annualise * 100,   # legacy: population std, percent
        "historical_vol_20d": logret.rolling(20).std(ddof=0) * annualise * 100,
        "rsi_14": 100 - 100 / (1 + gain / loss),
        "macd": macd,
        "macd_signal": macd.ewm(span=9, adjust=False).mean(),
        "bb_width": 4 * sd20 / sma20 * 100,                     # (upper - lower) / middle, percent
        "atr_14": atr14,
        "atr_pct": atr14 / c,
        "dist_ma50": c / c.rolling(50).mean() - 1,
        "drawdown_52w": c / c.rolling(TRADING_DAYS).max() - 1,
        "volume_ratio": v / v.rolling(20).mean(),
    })


def build_features(daily: pd.DataFrame, vix: pd.DataFrame, rates: pd.DataFrame,
                   anchors: Sequence) -> pd.DataFrame:
    """One row per anchor. `daily`: date/open/high/low/close/volume; `vix`: date/close; `rates`: date/rate."""
    if not len(anchors):
        return pd.DataFrame(columns=COLUMNS)
    ind = daily_indicators(daily)
    at = pd.DatetimeIndex(pd.to_datetime(list(anchors)))
    mondays = pd.DatetimeIndex([pd.Timestamp(monday_of(a.date())) for a in at])
    close = ind["close"]

    out = ind.reindex(at).drop(columns="close")
    c_anchor = close.reindex(at).to_numpy()
    c_prev_week = _asof(close, mondays, strict=True)                           # last close before this week
    c_prev_month = _asof(close, mondays - pd.Timedelta(days=21), strict=True)  # ... before 4 weeks ago
    out["ret_1w"] = np.log(c_anchor / c_prev_week)
    out["ret_4w"] = np.log(c_anchor / c_prev_month)

    week_of = pd.DatetimeIndex([pd.Timestamp(monday_of(d.date())) for d in close.index])
    highs = _series(daily, "high").groupby(week_of).max()
    lows = _series(daily, "low").groupby(week_of).min()
    out["range_1w"] = (highs.reindex(mondays).to_numpy() - lows.reindex(mondays).to_numpy()) / c_anchor
    out["weekly_change_pct"] = (c_anchor / c_prev_week - 1) * 100
    out["weekly_high_low_range_pct"] = out["range_1w"] * 100

    vix_s = _series(vix, "close")
    vix_now = _asof(vix_s, at)
    out["vix_close"] = vix_now
    out["vix_change_1w"] = vix_now - _asof(vix_s, mondays, strict=True)          # points since last week's close
    out["vix_hv_spread"] = vix_now - out["historical_vol_20d"].to_numpy()       # variance risk premium proxy
    rank = vix_s.rolling(TRADING_DAYS).apply(lambda w: (w <= w[-1]).mean(), raw=True)
    out["vix_pct_1y"] = _asof(rank, at)
    out["rate_3m"] = _asof(_series(rates, "rate"), at, strict=True)             # FRED posts a day late
    out["sessions_next"] = [sessions_next_week(a.date()) for a in at]

    out.insert(0, "anchor_date", [a.date() for a in at])
    out.insert(0, "week_start_date", [m.date() for m in mondays])
    return out.reset_index(drop=True)[list(COLUMNS)]
