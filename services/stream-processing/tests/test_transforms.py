from datetime import date, datetime

from jobs.schemas import CHAIN_PAYLOAD, DAILY_PAYLOAD
from jobs.transforms import chain_rows, daily_frames, parse_envelopes


def chain_msg(expiry="2026-10-09", quoted_at="2026-10-05T20:14:59Z", bid=40.5, strikes=(7770.0, 7775.0),
              volume=10, open_interest=None):
    return {
        "schema": "chain.v1", "source": "cboe", "delay_minutes": 15, "produced_at": "2026-10-06T05:06:02.878955Z",
        "payload": {
            "symbol": "SPX", "expiry": expiry, "session_date": "2026-10-05", "quoted_at": quoted_at,
            "underlying_price": 7773.95,
            "quotes": [
                {"option_type": t, "strike": k, "bid": bid, "ask": None if bid is None else bid + 0.4, "last": None,
                 "volume": volume, "open_interest": open_interest, "vendor_iv": 0.11, "vendor_delta": 0.5}
                for k in strikes for t in ("C", "P")
            ],
        },
    }


def daily_msg(dataset, day, produced_at="2026-10-06T05:06:04.283112Z", **fields):
    symbol = {"underlying": "SPX", "vix": "VIX", "rates": "DGS3MO"}[dataset]
    return {"schema": "daily.v1", "source": "x", "delay_minutes": 0, "produced_at": produced_at,
            "payload": {"dataset": dataset, "symbol": symbol, "date": day, **fields}}


def test_bad_messages_are_rejected(kafka_df):
    batch = kafka_df(chain_msg(), "not json", {**chain_msg(), "schema": "chain.v2"}, {"schema": "chain.v1"})
    valid, rejected = parse_envelopes(batch, CHAIN_PAYLOAD, "chain.v1")
    assert valid.count() == 1 and rejected.count() == 3


def test_microsecond_timestamps_parse(kafka_df):
    valid, _ = parse_envelopes(kafka_df(chain_msg()), CHAIN_PAYLOAD, "chain.v1")
    row = valid.first()
    assert row.produced_at == datetime(2026, 10, 6, 5, 6, 2, 878955)
    assert row.payload.quoted_at == datetime(2026, 10, 5, 20, 14, 59)


def test_chain_explodes_to_one_row_per_contract(kafka_df):
    valid, _ = parse_envelopes(kafka_df(chain_msg(), chain_msg(expiry="2026-10-12")), CHAIN_PAYLOAD, "chain.v1")
    rows = chain_rows(valid).collect()
    assert len(rows) == 8                                         # 2 expiries x 2 strikes x C/P
    r = next(r for r in rows if r.expiry_date == date(2026, 10, 9) and r.strike == 7775.0 and r.option_type == "P")
    assert (r.symbol, r.snapshot_date, r.source, r.bid, r.open_interest) == ("SPX", date(2026, 10, 5), "cboe", 40.5, None)


def test_newest_quote_per_contract_wins_within_a_batch(kafka_df):
    older = chain_msg(quoted_at="2026-10-05T19:00:00Z", bid=30.0)
    newer = chain_msg(quoted_at="2026-10-05T20:14:59Z", bid=40.5)
    valid, _ = parse_envelopes(kafka_df(newer, older), CHAIN_PAYLOAD, "chain.v1")
    rows = chain_rows(valid).collect()
    assert len(rows) == 4 and {r.bid for r in rows} == {40.5}


def test_quote_less_capture_keeps_the_earlier_quote_within_a_batch(kafka_df):
    good = chain_msg(quoted_at="2026-10-05T19:43:00Z", bid=40.5, volume=900, open_interest=1200)
    empty = chain_msg(quoted_at="2026-10-05T20:14:59Z", bid=None, volume=1500, open_interest=1250)
    valid, _ = parse_envelopes(kafka_df(empty, good), CHAIN_PAYLOAD, "chain.v1")
    rows = chain_rows(valid).collect()
    assert len(rows) == 4
    assert {(r.bid, r.quoted_at) for r in rows} == {(40.5, datetime(2026, 10, 5, 19, 43))}   # the real quote
    assert {(r.volume, r.open_interest) for r in rows} == {(1500, 1250)}                    # newest OI/volume


def test_only_quote_less_captures_still_give_a_row(kafka_df):
    valid, _ = parse_envelopes(kafka_df(chain_msg(bid=None)), CHAIN_PAYLOAD, "chain.v1")
    assert [r.bid for r in chain_rows(valid).collect()] == [None] * 4


def test_bad_contracts_are_dropped(kafka_df):
    msg = chain_msg()
    msg["payload"]["quotes"].append({"option_type": "X", "strike": 7780.0})
    msg["payload"]["quotes"].append({"option_type": "C", "strike": -5.0})
    valid, _ = parse_envelopes(kafka_df(msg), CHAIN_PAYLOAD, "chain.v1")
    assert chain_rows(valid).count() == 4


def test_daily_split_and_newest_message_per_day(kafka_df):
    batch = kafka_df(
        daily_msg("underlying", "2026-10-02", open=1.0, high=2.0, low=0.5, close=1.5, volume=10),
        daily_msg("underlying", "2026-10-02", produced_at="2026-10-07T00:00:00Z", open=1.0, high=2.0, low=0.5, close=1.6, volume=12),
        daily_msg("underlying", "2026-10-05", close=9.0),                     # missing OHLC: dropped
        daily_msg("vix", "2026-10-02", close=16.4),
        daily_msg("rates", "2026-10-01", rate=0.0412),
    )
    valid, _ = parse_envelopes(batch, DAILY_PAYLOAD, "daily.v1")
    underlying, vix, rates = daily_frames(valid)
    assert [tuple(r) for r in underlying.collect()] == [("SPX", date(2026, 10, 2), 1.0, 2.0, 0.5, 1.6, 12)]
    assert [tuple(r) for r in vix.collect()] == [(date(2026, 10, 2), 16.4)]
    assert [tuple(r) for r in rates.collect()] == [(date(2026, 10, 1), 0.0412)]
