from datetime import date, datetime

import pytest

from jobs.optionsdx import (EXPECTED_COLUMNS, check_headers, classify, expiry_map_frame, kept_rows, map_expiry,
                            parse_header, typed)

HEADER = ", ".join(f"[{c}]" for c in EXPECTED_COLUMNS)


def test_header_check():
    assert parse_header(HEADER) == EXPECTED_COLUMNS
    check_headers({"a.txt": HEADER})
    with pytest.raises(ValueError, match="b.txt.*missing \\['C_IV'\\]"):
        check_headers({"a.txt": HEADER, "b.txt": HEADER.replace("[C_IV], ", "")})


@pytest.mark.parametrize("label,expected", [
    (date(2010, 1, 14), (date(2010, 1, 15), True)),      # Jan 2010 monthly, labelled by its last trading day
    (date(2010, 1, 7), (date(2010, 1, 8), True)),        # 2010 weekly: same convention
    (date(2019, 6, 20), (date(2019, 6, 21), True)),      # monthly
    (date(2023, 3, 16), (date(2023, 3, 16), False)),     # 2023: Thursday is a listed expiry itself
    (date(2019, 4, 18), (date(2019, 4, 18), False)),     # Good Friday 2019: the Thursday is the expiry
    (date(2014, 6, 30), (date(2014, 6, 30), False)),     # end-of-quarter Monday: real contract, kept as labelled
    (date(2016, 3, 2), (date(2016, 3, 2), False)),       # Wednesday weekly (2016): kept
    (date(2010, 11, 25), (date(2010, 11, 26), True)),    # Thanksgiving Thursday label -> Friday's expiry
    (date(2010, 1, 9), None),                            # a Saturday can't be an expiry
])
def test_map_expiry(label, expected):
    assert map_expiry(label) == expected


def row(**over):
    values = {c: "" for c in EXPECTED_COLUMNS}
    values.update({
        "QUOTE_READTIME": "2010-01-04 16:00", "QUOTE_DATE": "2010-01-04", "UNDERLYING_LAST": "1132.990000",
        "EXPIRE_DATE": "2010-01-14", "DTE": "10.000000", "STRIKE": "1130.000000",
        "C_BID": "18.500000", "C_ASK": "19.300000", "C_LAST": "18.900000", "C_VOLUME": "120.000000",
        "C_IV": "0.180000", "C_DELTA": "0.540000",
        "P_BID": "15.100000", "P_ASK": "15.900000", "P_LAST": "", "P_VOLUME": "",
        "P_IV": "0.190000", "P_DELTA": "-0.460000",
    })
    values.update(over)
    return tuple(values[c] for c in EXPECTED_COLUMNS)


def classified(spark, *rows, max_dte=60, moneyness=0.10):
    raw = spark.createDataFrame(list(rows), ", ".join(f"{c} string" for c in EXPECTED_COLUMNS))
    wide = typed(raw)
    labels = [r.label for r in wide.select("label").distinct().collect() if r.label]
    wide = wide.join(expiry_map_frame(spark, labels), "label", "left")
    return classify(wide, max_dte, moneyness)


def test_unpivot_and_types(spark):
    rows = kept_rows(classified(spark, row())).collect()
    assert [(r.option_type, r.expiry_date) for r in sorted(rows, key=lambda r: r.option_type)] == [
        ("C", date(2010, 1, 15)), ("P", date(2010, 1, 15))]
    call = next(r for r in rows if r.option_type == "C")
    assert (call.symbol, call.source, call.strike, call.bid, call.volume, call.vendor_iv) == ("SPX", "optionsdx", 1130.0, 18.5, 120, 0.18)
    assert call.open_interest is None                                        # not in the files: unknown
    assert call.quoted_at == datetime(2010, 1, 4, 21, 0)                     # 16:00 ET = 21:00 UTC in January
    put = next(r for r in rows if r.option_type == "P")
    assert put.last is None and put.volume is None                           # blank cells -> NULL


def test_statuses(spark):
    rows = classified(
        spark,
        row(),                                                              # kept x2
        row(STRIKE="1300.000000"),                                          # >10% from spot
        row(EXPIRE_DATE="2010-04-15", DTE="101.000000"),                    # beyond 60 DTE
        row(STRIKE="1135.000000", C_BID="0.000000", P_ASK=""),              # no two-sided quote (both sides)
        row(STRIKE="1140.000000", EXPIRE_DATE="2010-01-16"),                # Saturday label
    ).groupBy("status").count().collect()
    assert {r.status: r["count"] for r in rows} == {
        "kept": 2, "filtered: moneyness": 2, "filtered: dte": 2,
        "rejected: no two-sided quote": 2, "rejected: expiry not a trading day": 2,
    }


def test_real_friday_label_beats_a_shifted_thursday(spark):
    shifted = row(EXPIRE_DATE="2010-01-14", C_BID="1.000000", C_ASK="2.000000")
    real = row(EXPIRE_DATE="2010-01-15", C_BID="18.500000", C_ASK="19.300000")
    calls = [r for r in kept_rows(classified(spark, shifted, real)).collect() if r.option_type == "C"]
    assert [(r.expiry_date, r.bid) for r in calls] == [(date(2010, 1, 15), 18.5)]
