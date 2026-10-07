from datetime import date, datetime, timedelta, timezone

from app import market_spec
from app.gaps.detector import (DAILY_START, INTERVALS, OPTIONSDX_END, SYMBOLS, Coverage, find_gaps,
                               known_ranges)
from app.gaps.expected import closed_sessions, expected_bars, in_source_window, min_bars

NOW = datetime(2026, 10, 6, 22, 0, tzinfo=timezone.utc)       # Tue 18:00 ET, after the close
COLLECTION_START = date(2026, 10, 1)


def full_coverage(now=NOW) -> Coverage:
    """Everything the detector checks, complete."""
    sessions = closed_sessions(DAILY_START, now)
    cov = Coverage(daily=set(sessions), vix=set(sessions), rates=set(sessions), collection_start=COLLECTION_START,
                   chain={d for d in sessions if d <= OPTIONSDX_END or d >= COLLECTION_START})
    for symbol in SYMBOLS:
        for interval in INTERVALS:
            cov.bars[(symbol, interval)] = {d: expected_bars(d, interval) for d in sessions
                                            if in_source_window(d, interval, now)}
    return cov


def keys(gaps):
    return [(g.dataset, g.symbol, g.gap_date) for g in gaps]


def test_complete_data_has_no_gaps():
    assert find_gaps(full_coverage(), NOW) == []


def test_missing_daily_row():
    cov = full_coverage()
    cov.daily.discard(date(2026, 9, 15))
    assert keys(find_gaps(cov, NOW)) == [("daily", "SPX", date(2026, 9, 15))]


def test_session_is_not_checked_until_after_the_close():
    cov = full_coverage()
    cov.daily.discard(date(2026, 10, 6))
    assert find_gaps(cov, datetime(2026, 10, 6, 20, 30, tzinfo=timezone.utc)) == []   # 16:30 ET: too early
    assert keys(find_gaps(cov, NOW)) == [("daily", "SPX", date(2026, 10, 6))]


def test_vix_may_lag_one_session():
    cov = full_coverage()
    cov.vix.discard(date(2026, 10, 6))
    assert find_gaps(cov, NOW) == []
    cov.vix.discard(date(2026, 10, 5))
    assert keys(find_gaps(cov, NOW)) == [("vix", "VIX", date(2026, 10, 5))]


def test_rates_only_flag_runs_longer_than_three_sessions():
    cov = full_coverage()
    three = [date(2026, 9, 14), date(2026, 9, 15), date(2026, 9, 16)]
    cov.rates -= set(three)
    assert find_gaps(cov, NOW) == []
    cov.rates.discard(date(2026, 9, 17))
    gaps = find_gaps(cov, NOW)
    assert keys(gaps) == [("rates", "DGS3MO", d) for d in three + [date(2026, 9, 17)]]
    assert gaps[0].detail == "rate missing 4 sessions in a row"


def test_intraday_short_session_is_a_gap():
    cov = full_coverage()
    cov.bars[("VIX", "1m")][date(2026, 9, 15)] = 389            # Yahoo's usual VIX count: fine
    cov.bars[("SPX", "5m")][date(2026, 9, 15)] = 77             # fine
    cov.bars[("SPX", "1m")][date(2026, 9, 16)] = 200
    del cov.bars[("VIX", "1h")][date(2026, 9, 17)]
    gaps = find_gaps(cov, NOW)
    assert keys(gaps) == [("intraday", "SPX:1m", date(2026, 9, 16)), ("intraday", "VIX:1h", date(2026, 9, 17))]
    assert [g.detail for g in gaps] == ["bars 200/390", "bars 0/7"]


def test_expected_bars_on_early_close():
    black_friday = date(2025, 11, 28)                           # 13:00 close
    assert [expected_bars(black_friday, i) for i in INTERVALS] == [210, 42, 4]
    assert min_bars(black_friday, "1h") == 3                    # SPX has 3 hourly bars on early closes
    assert [min_bars(date(2026, 9, 15), i) for i in INTERVALS] == [382, 76, 6]


def test_intraday_outside_yahoos_window_is_not_checked():
    assert in_source_window(date(2026, 9, 15), "1m", NOW)
    assert not in_source_window(date(2026, 8, 20), "1m", NOW)  # ~47 days back; 1m keeps 30
    assert in_source_window(date(2026, 8, 20), "5m", NOW)
    cov = full_coverage()
    cov.bars[("SPX", "1m")] = {}                                # no 1m at all: only the last ~30 days are gaps
    gaps = find_gaps(cov, NOW)
    in_window = [d for d in market_spec.trading_days(date(2026, 8, 1), NOW.date()) if in_source_window(d, "1m", NOW)]
    assert [g.gap_date for g in gaps] == in_window and len(in_window) in (20, 21, 22)


def test_chain_gaps_skip_known_ranges():
    cov = full_coverage()
    for d in (date(2015, 6, 1), date(2010, 2, 1), date(2025, 3, 3), date(2026, 10, 2)):
        cov.chain.discard(d)
    # 2010-02-01 (blank OptionsDX files) is known; 2025-03-03 is in the synthetic-only years (not in cov.chain anyway).
    assert keys(find_gaps(cov, NOW)) == [("chain", "SPX", date(2015, 6, 1)), ("chain", "SPX", date(2026, 10, 2))]


def test_known_ranges_end_where_collection_starts():
    synthetic = known_ranges(full_coverage(), NOW.date())[-1]
    assert (synthetic.start, synthetic.end) == (date(2024, 1, 1), COLLECTION_START - timedelta(days=1))
    assert known_ranges(Coverage(), NOW.date())[-1].end == NOW.date()   # nothing collected yet
