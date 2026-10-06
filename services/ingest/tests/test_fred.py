from datetime import date

import pytest

from app.sources.fred import DailyRate, fetch_rates

CSV = """observation_date,DGS3MO
2026-10-09,4.21
2026-10-12,
2026-10-13,.
2026-10-14,4.18
"""


def test_rates_skip_bond_holidays_and_convert_percent():
    rows = fetch_rates(get_text=lambda url: CSV)
    assert [r.date for r in rows] == [date(2026, 10, 9), date(2026, 10, 14)]   # Columbus Day blank, '.' skipped
    assert rows[0].rate == pytest.approx(0.0421)


def test_rates_date_filter():
    assert fetch_rates(start=date(2026, 10, 10), get_text=lambda url: CSV) == [DailyRate(date(2026, 10, 14), 0.0418)]
