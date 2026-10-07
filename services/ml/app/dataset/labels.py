"""Next-week labels: what happened between one anchor's close and the next.

For anchor A (this week's last close) and N, the anchor of the following week:
    close_ret  ln(close[N] / close[A])                  the expiry close: what the forecast targets
    high_ret   ln(max high over (A, N] / close[A])      how far up it went during the week (touch risk)
    low_ret    ln(min low  over (A, N] / close[A])      how far down
    sessions   sessions between them

A week gets no label when the next week isn't complete yet (the latest anchor), when the next week
has no anchor in the data, or when the data is missing a session of it: a high/low from a partial
week would understate the range.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Sequence

import numpy as np
import pandas as pd

from .weeks import monday_of, sessions_in_week

COLUMNS = ("anchor_date", "next_anchor_date", "sessions", "close_ret", "high_ret", "low_ret")


def build_labels(daily: pd.DataFrame, anchors: Sequence) -> pd.DataFrame:
    d = daily.sort_values("date")
    dates = pd.to_datetime(d["date"]).to_numpy()
    close, high, low = (d[k].astype(float).to_numpy() for k in ("close", "high", "low"))
    by_monday = {monday_of(a): a for a in anchors}

    rows = []
    for a in anchors:
        n = by_monday.get(monday_of(a) + timedelta(days=7))
        if n is None:
            continue
        start = np.searchsorted(dates, np.datetime64(a), side="right")     # first session after A
        end = np.searchsorted(dates, np.datetime64(n), side="right")       # through N
        if end - start != sessions_in_week(n):                              # a session of next week is missing
            continue
        c_a = close[start - 1]
        rows.append((a, n, end - start, np.log(close[end - 1] / c_a),
                     np.log(high[start:end].max() / c_a), np.log(low[start:end].min() / c_a)))
    return pd.DataFrame(rows, columns=COLUMNS)
