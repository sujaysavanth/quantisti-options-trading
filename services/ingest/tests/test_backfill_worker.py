import json
from contextlib import contextmanager
from datetime import date, datetime, timezone

from app.backfill.consumer import BackfillConsumer
from app.backfill.intraday import RangeResult
from app.backfill.worker import Worker
from app.gaps import scan as scan_mod
from app.producers.envelope import BackfillPayload
from app.producers.kafka import Publisher
from app.sources.cboe import DailyClose
from app.sources.yahoo import DailyBar
from tests.fakes import FakeProducer

NOW = datetime(2026, 10, 6, 22, 0, tzinfo=timezone.utc)       # Tue 18:00 ET


def req(dataset, symbol, day, attempt=1):
    return BackfillPayload(dataset=dataset, symbol=symbol, date=day, attempt=attempt)


def worker(**kwargs):
    fake = FakeProducer()
    return Worker(Publisher("unused", producer=fake), **kwargs), fake


# ---------------------------------------------------------------- Worker

def test_daily_row_is_published_to_market_daily():
    w, fake = worker(fetch_spx=lambda s, a, b: [DailyBar(a, 6600.0, 6650.0, 6590.0, 6640.0, 10)])
    out = w.handle(req("daily", "SPX", date(2026, 9, 15)), NOW)
    assert (out.kind, out.sent) == ("published", 1)
    topic, key, msg = fake.sent[0]
    assert (topic, key, msg["schema"], msg["payload"]["date"]) == ("market.daily", "underlying:SPX", "daily.v1", "2026-09-15")


def test_source_without_the_row_is_a_failure_not_a_fill():
    w, fake = worker(fetch_vix=lambda start, end: [])
    out = w.handle(req("vix", "VIX", date(2026, 9, 15)), NOW)
    assert out.kind == "failed" and "no VIX close" in out.detail and fake.sent == []


def test_vix_and_errors():
    w, _ = worker(fetch_vix=lambda start, end: [DailyClose(start, 16.2)],
                  fetch_rates=lambda start, end: (_ for _ in ()).throw(RuntimeError("FRED down")))
    assert w.handle(req("vix", "VIX", date(2026, 9, 15)), NOW).kind == "published"
    out = w.handle(req("rates", "DGS3MO", date(2026, 9, 15)), NOW)
    assert (out.kind, out.detail) == ("failed", "RuntimeError: FRED down")


def test_intraday_fetches_the_whole_et_day_at_the_requested_size():
    calls = []
    w, _ = worker(fill_intraday=lambda pub, rng: calls.append(rng) or RangeResult(rng, bars=78))
    out = w.handle(req("intraday", "VIX:5m", date(2026, 9, 15)), NOW)
    assert (out.kind, out.sent) == ("published", 78)
    rng = calls[0]
    assert (rng.symbol, rng.interval) == ("VIX", "5m")
    assert (rng.start, rng.end) == (datetime(2026, 9, 15, 4, 0, tzinfo=timezone.utc),
                                    datetime(2026, 9, 16, 4, 0, tzinfo=timezone.utc))   # 00:00 ET to 00:00 ET


def test_intraday_beyond_yahoos_window_is_unrecoverable():
    w, _ = worker(fill_intraday=lambda pub, rng: (_ for _ in ()).throw(AssertionError("should not fetch")))
    out = w.handle(req("intraday", "SPX:1m", date(2026, 8, 20)), NOW)
    assert out.kind == "unrecoverable" and "30-day 1m window" in out.detail


def test_intraday_fetch_error_is_a_failure():
    w, _ = worker(fill_intraday=lambda pub, rng: RangeResult(rng, error="YFRateLimitError: too many requests"))
    assert w.handle(req("intraday", "SPX:1m", date(2026, 9, 15)), NOW).kind == "failed"


def test_past_chain_is_unrecoverable_current_one_is_polled():
    polls = []
    w, _ = worker(poll_chain=lambda: polls.append(1) or 12)
    assert w.handle(req("chain", "SPX", date(2026, 10, 2)), NOW).kind == "unrecoverable"
    assert polls == []
    out = w.handle(req("chain", "SPX", date(2026, 10, 6)), NOW)                # 18:00 ET: still today's session
    assert (out.kind, out.sent, polls) == ("published", 12, [1])


# ---------------------------------------------------------------- scan decisions

def test_decide():
    assert scan_mod.decide("requested", 0) == "request"
    assert scan_mod.decide("requested", 2) == "request"
    assert scan_mod.decide("requested", 3) == "give_up"
    assert scan_mod.decide("unrecoverable", 0) is None
    assert scan_mod.decide("filled", 0) is None


def test_scan_requests_gives_up_and_leaves_alone(monkeypatch):
    rows = [dict(dataset="daily", symbol="SPX", gap_date=date(2026, 9, 15), status="requested", attempts=0, detail="no daily row"),
            dict(dataset="vix", symbol="VIX", gap_date=date(2026, 9, 14), status="requested", attempts=3, detail="no VIX close"),
            dict(dataset="chain", symbol="SPX", gap_date=date(2026, 10, 2), status="unrecoverable", attempts=1, detail="x")]
    calls = []
    monkeypatch.setattr(scan_mod, "recheck", lambda conn: 2)
    monkeypatch.setattr(scan_mod.store, "load_coverage", lambda conn, now: None)
    monkeypatch.setattr(scan_mod.store, "upsert_gaps", lambda conn, gaps: rows)
    monkeypatch.setattr(scan_mod.store, "set_attempts", lambda conn, *a: calls.append(("attempts", *a)))
    monkeypatch.setattr(scan_mod.store, "set_status", lambda conn, *a: calls.append(("status", *a)))
    monkeypatch.setattr(scan_mod, "find_gaps", lambda cov, now: [])
    fake = FakeProducer()

    result = scan_mod.scan(None, Publisher("unused", producer=fake), NOW)

    assert (result.filled, result.requested, result.gave_up) == (2, 1, 1)
    assert calls[0] == ("attempts", "daily", "SPX", date(2026, 9, 15), 1)
    assert calls[1][:5] == ("status", "vix", "VIX", date(2026, 9, 14), "unrecoverable")
    (t1, k1, m1), (t2, k2, m2) = fake.sent
    assert (t1, k1, m1["schema"], m1["payload"]["attempt"]) == ("ingest.backfill.requests", "daily:2026-09-15", "backfill.v1", 1)
    assert (t2, k2, m2["job"]) == ("ingest.dlq", "ingest.backfill.requests", "gap_detector")
    assert json.loads(m2["value"])["payload"]["dataset"] == "vix"


# ---------------------------------------------------------------- consumer

class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))

    def fetchone(self):
        return self.conn.gap_row


class FakeConn:
    def __init__(self, gap_row):
        self.gap_row, self.executed = gap_row, []

    def cursor(self, **kwargs):
        return FakeCursor(self)


def consumer(gap_row, **worker_kwargs):
    fake = FakeProducer()
    pub = Publisher("unused", producer=fake)
    conn = FakeConn(gap_row)

    @contextmanager
    def connect_db():
        yield conn
    c = BackfillConsumer("unused", "unused", pub, Worker(pub, **worker_kwargs))
    return c, fake, conn, connect_db


def message(dataset="vix", symbol="VIX", day="2026-09-15", attempt=1):
    return json.dumps({"schema": "backfill.v1", "source": "gap_detector", "delay_minutes": 0,
                       "produced_at": "2026-10-06T22:00:00Z",
                       "payload": {"dataset": dataset, "symbol": symbol, "date": day, "attempt": attempt}}).encode()


def test_bad_requests_go_to_the_dlq():
    c, fake, _, connect_db = consumer(None)
    assert c.handle(b"not json", connect_db) == "dlq"
    assert c.handle(json.dumps({"schema": "backfill.v1", "payload": {"dataset": "nope"}}).encode(), connect_db) == "dlq"
    assert c.handle(message(dataset="intraday", symbol="SPX"), connect_db) == "dlq"   # needs SPX:1m
    assert [(t, k) for t, k, _ in fake.sent] == [("ingest.dlq", "ingest.backfill.requests")] * 3
    assert fake.sent[0][2]["job"] == "backfill_worker" and fake.sent[0][2]["value"] == "not json"


def test_stale_or_closed_requests_are_skipped():
    c, fake, _, connect_db = consumer(("filled", 1, "no VIX close"))
    assert c.handle(message(), connect_db) == "skipped"
    c, fake, _, connect_db = consumer(("requested", 2, "no VIX close"))
    assert c.handle(message(attempt=1), connect_db) == "skipped"                     # attempt 2 is the live one
    assert fake.sent == []


def test_handled_request_publishes_and_notes_the_attempt():
    c, fake, conn, connect_db = consumer(("requested", 1, "no VIX close"),
                                         fetch_vix=lambda start, end: [DailyClose(start, 16.2)])
    assert c.handle(message(), connect_db) == "published"
    assert fake.sent[0][0] == "market.daily"
    sql, params = conn.executed[-1]
    assert "UPDATE ingest_gaps" in sql and params[:2] == ("requested", "no VIX close | attempt 1: sent 1")
    assert c.handled["published"] == 1 and c.last["outcome"] == "published"


def test_unrecoverable_outcome_sets_the_status():
    c, _, conn, connect_db = consumer(("requested", 1, "no chain snapshot"))
    assert c.handle(message("chain", "SPX", "2026-10-02"), connect_db) == "unrecoverable"
    assert conn.executed[-1][1][:2] == ("unrecoverable", "no chain snapshot | attempt 1: no free source for past option chains")


def test_index_gap_is_refetched_from_its_source():
    from app.sources.indexes import IndexValue
    asked = []
    w, fake = worker(fetch_index=lambda s, a, b: asked.append((s.symbol, a, b)) or [IndexValue(s.symbol, a, 1.47)])
    out = w.handle(req("index", "BAA10Y", date(2026, 9, 15)), NOW)
    assert (out.kind, out.sent, asked) == ("published", 1, [("BAA10Y", date(2026, 9, 15), date(2026, 9, 15))])
    topic, key, msg = fake.sent[0]
    assert (topic, key, msg["source"], msg["payload"]["dataset"], msg["payload"]["close"]) == \
        ("market.daily", "index:BAA10Y", "fred", "index", 1.47)
    w, _ = worker(fetch_index=lambda s, a, b: [])
    assert w.handle(req("index", "VVIX", date(2026, 9, 15)), NOW).detail == "CBOE has no VVIX value for 2026-09-15"
    assert w.handle(req("index", "NOPE", date(2026, 9, 15)), NOW).kind == "failed"
