"""Which trading session a quote belongs to.

SPX options trade in two sessions per trading day D:
  - Global Trading Hours (GTH): 20:15 ET on the evening before D until 09:25 ET on D
  - Regular hours: 09:30-16:00 ET on D (13:00 on early-close days)
CBOE counts the overnight GTH session as part of D, so a quote taken at 01:45 ET
belongs to that same day, and one taken at 21:00 ET belongs to the *next* day.
On weekends and holidays nothing trades: quotes are left over from the last session.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from .. import market_spec

GTH_OPEN = time(20, 15)  # ET; from here on, quotes belong to the next session


def session_for(quoted_at: datetime) -> date:
    if quoted_at.tzinfo is None:
        raise ValueError("quoted_at must be timezone-aware")
    local = quoted_at.astimezone(market_spec.TZ)

    # After the GTH open, quotes are for tomorrow's session; before it, for today's.
    candidate = local.date() + timedelta(days=1) if local.time() >= GTH_OPEN else local.date()
    if market_spec.is_trading_day(candidate):
        return candidate

    # Weekend or holiday: the quotes still on the screen are from the last session.
    return market_spec.trading_days(candidate - timedelta(days=10), candidate)[-1]
