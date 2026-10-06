"""Run any data source from the terminal and print what it returns (no Kafka, no database),
or run the Kafka producers once.

    python -m app.cli fetch-chain --expiries 1 --limit 6
    python -m app.cli fetch-chain --source yahoo --expiries 1 --limit 6
    python -m app.cli fetch-bars --symbol SPX --interval 1m --days 1 --limit 5
    python -m app.cli fetch-vix --days 7
    python -m app.cli fetch-rates --days 7
    python -m app.cli poll-once --all --force                          # inside the ingest container
    python -m app.cli poll-once --daily --bootstrap localhost:9094     # from your machine
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

    args = parser.parse_args(argv)
    if args.command == "poll-once" and not (args.intraday or args.chain or args.daily or args.all):
        parser.error("poll-once needs --intraday, --chain, --daily or --all")
    args.run(args)


if __name__ == "__main__":
    main()
