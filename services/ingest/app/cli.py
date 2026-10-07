"""Run any data source from the terminal and print what it returns (no Kafka, no database),
or run the Kafka producers once.

    python -m app.cli fetch-chain --expiries 1 --limit 6
    python -m app.cli fetch-chain --source yahoo --expiries 1 --limit 6
    python -m app.cli fetch-bars --symbol SPX --interval 1m --days 1 --limit 5
    python -m app.cli fetch-vix --days 7
    python -m app.cli fetch-rates --days 7
    python -m app.cli poll-once --all --force                          # inside the ingest container
    python -m app.cli poll-once --daily --bootstrap localhost:9094     # from your machine
    python -m app.cli backfill-intraday --max                          # all the intraday history Yahoo still has
    python -m app.cli backfill-intraday --days 5 --interval 1m --symbol SPX
    python -m app.cli backfill-daily --indexes --since 2010-01-01      # VIX9D, VIX3M, VVIX, SKEW, BAA10Y, T10Y2Y
    python -m app.cli scan-gaps --dry-run                              # print gaps, change nothing
    python -m app.cli scan-gaps                                        # same as POST /v1/gaps/scan
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone

from .config import get_settings
from .sources import chain_source


def _num(value, digits=2):
    return "-" if value is None else f"{value:,.{digits}f}"


def fetch_chain(args) -> None:
    snap = chain_source(args.source).fetch_chain(args.expiries, args.moneyness)
    print(f"source={snap.source} delay_minutes={snap.delay_minutes} session={snap.session_date} "
          f"quoted_at={snap.quoted_at:%Y-%m-%d %H:%M}Z spot={_num(snap.underlying_price)} contracts={len(snap.quotes)}")
    print(f"{'expiry':10} {'type':4} {'strike':>9} {'bid':>8} {'ask':>8} {'volume':>7} {'OI':>7} {'vendor_iv':>9}")
    for q in snap.quotes[: args.limit]:
        print(f"{q.expiry!s:10} {q.option_type:4} {q.strike:>9,.1f} {_num(q.bid):>8} {_num(q.ask):>8} "
              f"{q.volume if q.volume is not None else '-':>7} {q.open_interest if q.open_interest is not None else '-':>7} "
              f"{_num(q.vendor_iv, 4):>9}")


def fetch_bars(args) -> None:
    from .sources.yahoo import fetch_bars as get_bars
    now = datetime.now(timezone.utc)
    bars = get_bars(args.symbol, args.interval, now - timedelta(days=args.days), now)
    print(f"{args.symbol} {args.interval}: {len(bars)} bars")
    for b in bars[-args.limit:]:
        print(f"{b.ts:%Y-%m-%d %H:%M}Z  O {b.open:,.2f}  H {b.high:,.2f}  L {b.low:,.2f}  C {b.close:,.2f}  V {b.volume:,}")


def fetch_vix(args) -> None:
    from .sources.cboe import fetch_vix_history
    for row in fetch_vix_history(start=date.today() - timedelta(days=args.days)):
        print(f"{row.date}  VIX {row.close:.2f}")


def fetch_rates(args) -> None:
    from .sources.fred import fetch_rates as get_rates
    for row in get_rates(start=date.today() - timedelta(days=args.days)):
        print(f"{row.date}  3m T-bill {row.rate:.4%}")


def poll_once(args) -> None:
    from .producers.chain import ChainPoller
    from .producers.daily import DailyPoller
    from .producers.intraday import IntradayPoller
    from .producers.kafka import Publisher
    from .producers.schedule import is_market_open

    settings = get_settings()
    publisher = Publisher(args.bootstrap)
    if error := publisher.ping():
        raise SystemExit(f"Kafka at {args.bootstrap} is not reachable: {error}")
    market_open = is_market_open(datetime.now(timezone.utc))
    todo = {
        "intraday": (args.intraday or args.all, lambda: IntradayPoller(publisher).poll_once(), True),
        "chain": (args.chain or args.all, lambda: ChainPoller(publisher, chain_source(settings.CHAIN_SOURCE),
                  settings.CHAIN_EXPIRIES, settings.CHAIN_MONEYNESS).poll_once(force=True), True),
        "daily": (args.daily or args.all, lambda: DailyPoller(publisher).poll_once(), False),
    }
    for name, (wanted, run, needs_open_market) in todo.items():
        if not wanted:
            continue
        if needs_open_market and not market_open and not args.force:
            print(f"{name}: market closed, skipped (add --force to run anyway)")
            continue
        print(f"{name}: {run()} messages queued")
    left = publisher.flush(30)
    print(f"delivered {dict(publisher.delivered)}  failed {dict(publisher.failed)}  undelivered {left}")


def backfill_intraday(args) -> None:
    from .backfill.intraday import backfill, plan_ranges
    from .producers.kafka import Publisher

    publisher = Publisher(args.bootstrap)
    if error := publisher.ping():
        raise SystemExit(f"Kafka at {args.bootstrap} is not reachable: {error}")
    ranges = plan_ranges(datetime.now(timezone.utc), intervals=args.interval.split(","),
                         symbols=args.symbol.split(","), days=None if args.max else args.days)
    for res in backfill(publisher, ranges):
        r = res.range
        outcome = f"FAILED {res.error}" if res.error else f"{res.bars:,} bars"
        print(f"{r.symbol} {r.interval:>2} {r.start:%Y-%m-%d} .. {r.end:%Y-%m-%d}: {outcome}")
    left = publisher.flush(60)
    print(f"delivered {dict(publisher.delivered)}  failed {dict(publisher.failed)}  undelivered {left}")


def backfill_daily(args) -> None:
    """Index history through market.daily, the same path live end-of-day rows take."""
    from .producers.daily import DailyPoller
    from .producers.kafka import Publisher
    from .sources.indexes import BY_SYMBOL, INDEX_SERIES

    series = [BY_SYMBOL[s] for s in args.symbol.split(",")] if args.symbol else list(INDEX_SERIES)
    publisher = Publisher(args.bootstrap)
    if error := publisher.ping():
        raise SystemExit(f"Kafka at {args.bootstrap} is not reachable: {error}")
    poller = DailyPoller(publisher)
    end = date.today()
    for s in series:
        sent = poller.publish_indexes(args.since, end, datetime.now(timezone.utc), series=[s])
        print(f"{s.symbol:7} {s.source:5} {args.since} .. {end}: "
              + (f"FAILED {poller.index_errors[s.symbol]}" if s.symbol in poller.index_errors else f"{sent:,} rows"))
        publisher.flush(60)
    left = publisher.flush(120)
    print(f"delivered {dict(publisher.delivered)}  failed {dict(publisher.failed)}  undelivered {left}")


def scan_gaps(args) -> None:
    from collections import Counter

    from .db import connect
    from .gaps import store
    from .gaps.detector import find_gaps, known_ranges

    now = datetime.now(timezone.utc)
    with connect(args.database_url) as conn:
        if args.dry_run:
            cov = store.load_coverage(conn, now)
            gaps = find_gaps(cov, now)
            for k in known_ranges(cov, now.date()):
                print(f"known   {k.dataset:8} {k.start} .. {k.end}  {k.reason}")
            print(f"{len(gaps)} gaps: {dict(Counter(g.dataset for g in gaps))}")
            for g in gaps[-args.limit:]:
                print(f"{g.gap_date}  {g.dataset:8} {g.symbol:7} {g.detail}")
            return

        from .gaps.scan import scan
        from .producers.kafka import Publisher
        publisher = Publisher(args.bootstrap)
        if error := publisher.ping():
            raise SystemExit(f"Kafka at {args.bootstrap} is not reachable: {error}")
        print(vars(scan(conn, publisher, now)))


def main(argv=None) -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Fetch market data and print it")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("fetch-chain", help="SPX option chain")
    p.add_argument("--source", choices=["cboe", "yahoo"], default=settings.CHAIN_SOURCE)
    p.add_argument("--expiries", type=int, default=settings.CHAIN_EXPIRIES)
    p.add_argument("--moneyness", type=float, default=settings.CHAIN_MONEYNESS)
    p.add_argument("--limit", type=int, default=20, help="rows to print")
    p.set_defaults(run=fetch_chain)

    p = sub.add_parser("fetch-bars", help="intraday bars from Yahoo")
    p.add_argument("--symbol", choices=["SPX", "VIX"], default="SPX")
    p.add_argument("--interval", choices=["1m", "5m", "1h"], default="1m")
    p.add_argument("--days", type=float, default=1)
    p.add_argument("--limit", type=int, default=10, help="most recent bars to print")
    p.set_defaults(run=fetch_bars)

    for name, run in (("fetch-vix", fetch_vix), ("fetch-rates", fetch_rates)):
        p = sub.add_parser(name)
        p.add_argument("--days", type=int, default=7)
        p.set_defaults(run=run)

    p = sub.add_parser("poll-once", help="run pollers once and publish to Kafka")
    for name in ("intraday", "chain", "daily", "all"):
        p.add_argument(f"--{name}", action="store_true")
    p.add_argument("--force", action="store_true", help="run intraday/chain even when the market is closed")
    p.add_argument("--bootstrap", default=settings.KAFKA_BOOTSTRAP, help="localhost:9094 from your machine")
    p.set_defaults(run=poll_once)

    p = sub.add_parser("backfill-intraday", help="publish historical 1m/5m/1h bars from Yahoo to Kafka")
    window = p.add_mutually_exclusive_group(required=True)
    window.add_argument("--max", action="store_true", help="as far back as Yahoo serves each interval")
    window.add_argument("--days", type=float, help="only the last N days (capped at Yahoo's window)")
    p.add_argument("--interval", default="1h,5m,1m", help="comma-separated: 1m,5m,1h")
    p.add_argument("--symbol", default="SPX,VIX", help="comma-separated: SPX,VIX")
    p.add_argument("--bootstrap", default=settings.KAFKA_BOOTSTRAP, help="localhost:9094 from your machine")
    p.set_defaults(run=backfill_intraday)

    p = sub.add_parser("backfill-daily", help="publish index history (VIX9D, VIX3M, VVIX, SKEW, BAA10Y, T10Y2Y) to Kafka")
    p.add_argument("--indexes", action="store_true", required=True, help="the index series (the only dataset for now)")
    p.add_argument("--since", type=date.fromisoformat, default=date(2010, 1, 1))
    p.add_argument("--symbol", help="comma-separated subset, e.g. VIX9D,BAA10Y")
    p.add_argument("--bootstrap", default=settings.KAFKA_BOOTSTRAP, help="localhost:9094 from your machine")
    p.set_defaults(run=backfill_daily)

    p = sub.add_parser("scan-gaps", help="find missing data; request backfills (or only print with --dry-run)")
    p.add_argument("--dry-run", action="store_true", help="print the gaps; write nothing, publish nothing")
    p.add_argument("--limit", type=int, default=30, help="most recent gaps to print with --dry-run")
    p.add_argument("--database-url", default=settings.DATABASE_URL,
                   help="postgresql://quantisti:quantisti@localhost:5432/quantisti from your machine")
    p.add_argument("--bootstrap", default=settings.KAFKA_BOOTSTRAP, help="localhost:9094 from your machine")
    p.set_defaults(run=scan_gaps)

    args = parser.parse_args(argv)
    if args.command == "poll-once" and not (args.intraday or args.chain or args.daily or args.all):
        parser.error("poll-once needs --intraday, --chain, --daily or --all")
    args.run(args)


if __name__ == "__main__":
    main()
