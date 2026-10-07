from datetime import date

import pytest

from app.sources.cboe import INDEX_HISTORY_URL, parse_index_history
from app.sources.fred import SERIES_URL, parse_series
from app.sources.indexes import BY_SYMBOL, INDEX_SERIES, fetch_index

# The two CSV layouts CBOE uses (checked 2026-10-07): OHLC files and single-column files.
OHLC = "DATE,OPEN,HIGH,LOW,CLOSE\n10/02/2026,12.10,12.80,11.90,12.62\n10/05/2026,12.62,13.00,12.00,\n10/06/2026,12.6,12.97,11.97,12.62\n"
SINGLE = "DATE,VVIX\n10/02/2026,80.10\n10/06/2026,82.59\n"
FRED = "observation_date,BAA10Y\n2026-10-02,1.47\n2026-10-05,\n2026-10-06,1.46\n"


def test_cboe_ohlc_layout_skips_blank_closes():
    rows = parse_index_history(OHLC)
    assert [(r.date, r.close) for r in rows] == [(date(2026, 10, 2), 12.62), (date(2026, 10, 6), 12.62)]


def test_cboe_single_column_layout():
    rows = parse_index_history(SINGLE, start=date(2026, 10, 3))
    assert [(r.date, r.close) for r in rows] == [(date(2026, 10, 6), 82.59)]


def test_fred_series_keep_their_own_units():
    assert [(r.date, r.value) for r in parse_series(FRED)] == [(date(2026, 10, 2), 1.47), (date(2026, 10, 6), 1.46)]


@pytest.mark.parametrize("symbol,body,url", [
    ("VVIX", SINGLE, INDEX_HISTORY_URL.format(symbol="VVIX")),
    ("BAA10Y", FRED, SERIES_URL.format(series="BAA10Y")),
])
def test_fetch_index_picks_the_right_source(symbol, body, url):
    asked = []
    rows = fetch_index(BY_SYMBOL[symbol], get_text=lambda u: asked.append(u) or body)
    assert asked == [url] and rows[-1].symbol == symbol and rows[-1].date == date(2026, 10, 6)


def test_series_list():
    assert [s.symbol for s in INDEX_SERIES] == ["VIX9D", "VIX3M", "VVIX", "SKEW", "BAA10Y", "T10Y2Y"]
    assert {s.gap_rule for s in INDEX_SERIES if s.source == "fred"} == {"runs"}
    assert BY_SYMBOL["VIX9D"].start == date(2011, 1, 4)                     # CBOE's history starts here
