"""Command line for the ML service.

    python -m app.cli build-dataset                                # build all weeks, store them, print a report
    python -m app.cli build-dataset --export ../../data/ml/weekly.csv
    python -m app.cli build-dataset --no-write                     # report only, change nothing
    python -m app.cli evaluate                                     # baselines, walk-forward -> data/ml/reports/

From your machine add --database-url postgresql://quantisti:quantisti@localhost:5432/quantisti.
"""

from __future__ import annotations

import argparse
import math
from datetime import date
from pathlib import Path

import numpy as np
import psycopg2

from .config import get_settings
from .dataset import store
from .dataset.features import CORE_FEATURES, FEATURE_GROUPS

Z80 = 1.2816   # 10% / 90% quantiles of a standard normal


def coverage_by_group(data) -> None:
    """Share of training weeks with each feature group present, overall and per era."""
    eras = {"2011-2023": data["anchor_date"].map(lambda d: d.year <= 2023),
            "2024-now": data["anchor_date"].map(lambda d: d.year >= 2024)}
    print(f"{'feature group':20} {'features':>8} " + " ".join(f"{e:>10}" for e in eras))
    for group, cols in FEATURE_GROUPS.items():
        present = data[list(cols)].notna().all(axis=1)
        print(f"{group:20} {len(cols):>8} " + " ".join(f"{present[m].mean():>10.0%}" for m in eras.values()))


def report(features, labels) -> None:
    complete = features.dropna(subset=list(CORE_FEATURES))
    data = complete.merge(labels, on="anchor_date")
    print(f"weeks: {len(features)} ({features['anchor_date'].min()} .. {features['anchor_date'].max()}), "
          f"with all core features: {len(complete)} (from {complete['anchor_date'].min()}), "
          f"usable for training (features + label): {len(data)}")
    if data.empty:
        return
    coverage_by_group(data)
    r = data["close_ret"]
    q = np.percentile(r, [5, 10, 50, 90, 95]) * 100
    print(f"next-week close return: mean {r.mean() * 100:+.2f}%  std {r.std() * 100:.2f}% "
          f"(annualised {r.std() * math.sqrt(52) * 100:.1f}%)  "
          f"q05/q10/q50/q90/q95 {' / '.join(f'{x:+.2f}%' for x in q)}")
    print(f"next-week high / low excursion: median {data['high_ret'].median() * 100:+.2f}% / "
          f"{data['low_ret'].median() * 100:+.2f}%")
    # First look only (Module 2 does this properly, year by year): the range VIX implies.
    sigma_vix = data["vix_close"] / 100 * np.sqrt(data["sessions"] / 252)
    inside = (r.abs() <= Z80 * sigma_vix).mean()
    print(f"VIX-implied weekly vol: mean {sigma_vix.mean() * 100:.2f}% vs realised {r.std() * 100:.2f}%; "
          f"its 80% band contained the close in {inside:.1%} of weeks")


def build_dataset(args) -> None:
    with psycopg2.connect(args.database_url) as conn:
        features, labels = store.build(conn)
        oi = store.build_oi_levels(conn)
        if not args.no_write:
            n_features, n_labels = store.save(conn, features, labels)
            n_oi = store.save_oi_levels(conn, oi)
            print(f"stored {n_features} weeks of features, {n_labels} labels, {n_oi} weeks of open-interest levels")
    report(features, labels)
    if args.export:
        out = features.merge(labels, on="anchor_date", how="left")
        Path(args.export).parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(args.export, index=False)
        print(f"exported {len(out)} rows to {args.export}")


def default_reports_dir() -> Path:
    """data/ml/reports at the repo root (git-ignored) when run from a checkout, else under the working directory."""
    root = Path(__file__).resolve().parents[3]
    return (root if (root / "services").is_dir() else Path.cwd()) / "data" / "ml" / "reports"


def training_rows(features, labels):
    """Weeks with every core feature and a label: what forecasters are fitted and scored on.
    Option features may be missing (no real chains 2024 .. Sep 2026); models must handle that."""
    return features.dropna(subset=list(CORE_FEATURES)).merge(labels, on="anchor_date")


def evaluate(args) -> None:
    from .evaluation import report, walkforward
    from .evaluation.baselines import Context, all_baselines, straddle_sigma

    with psycopg2.connect(args.database_url) as conn:
        features, labels = store.build(conn)
        daily, _, _ = store.load_market(conn)
        data = training_rows(features, labels)
        pairs = list(zip(data["anchor_date"], data["next_anchor_date"]))
        chains = store.load_anchor_chains(conn, pairs, moneyness=0.01)
    ctx = Context(daily[["date", "close"]], straddle_sigma(chains))
    print(f"{len(data)} weeks ({data['anchor_date'].min()} .. {data['anchor_date'].max()}), "
          f"ATM straddle found for {len(ctx.straddle_sigma)} weeks")

    baselines = all_baselines()
    last_year = max(a.year for a in data["anchor_date"])
    preds = walkforward.run(data, ctx, baselines, range(args.first_test_year, last_year + 1))
    summary = report.summarize(preds, [b.name for b in baselines])
    paths = report.write(summary, Path(args.out) if args.out else default_reports_dir())
    print("\n".join(report.table(summary["overall"])))
    print("\nwritten: " + ", ".join(str(p) for p in paths))


def oi_levels(args) -> None:
    """Any day's levels, not just anchors: lets you look at the recorder before the first weekly anchor has OI."""
    from datetime import timedelta

    from .dataset.oi_levels import oi_levels as compute
    from .dataset.weeks import anchor_of_week

    expiry = args.expiry or anchor_of_week(args.date)                     # this week's expiry if still ahead...
    if expiry is None or expiry <= args.date:
        expiry = anchor_of_week(args.date + timedelta(days=7))           # ...else next week's (as for anchors)
    with psycopg2.connect(args.database_url) as conn:
        chain = store.load_anchor_chains(conn, [(args.date, expiry)], sources=("cboe",))
    levels = compute(chain, max((expiry - args.date).days, 1) / 365)
    if not levels:
        raise SystemExit(f"no CBOE open interest for the {expiry} expiry on {args.date}")
    def fmt(value, spec=",.0f", scale=1.0, suffix=""):
        return "n/a" if value is None else f"{value / scale:{spec}}{suffix}"

    print(f"{args.date} -> expiry {expiry}: spot {fmt(levels['spot'], ',.2f')}  put wall {fmt(levels['put_wall'])}  "
          f"call wall {fmt(levels['call_wall'])}  max pain {fmt(levels['max_pain'])}  "
          f"GEX {fmt(levels['gex'], '+.2f', 1e9, 'bn $ per 1%')}  "
          f"({levels['contracts']:,} contracts, strikes within 5% of spot)")
    if levels["gex"] is None:
        print("GEX needs implied vols; this capture has none")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build-dataset", help="weekly features + next-week labels for every complete week")
    p.add_argument("--database-url", default=get_settings().DATABASE_URL)
    p.add_argument("--export", help="also write features + labels to this CSV (data/ is git-ignored)")
    p.add_argument("--no-write", action="store_true", help="don't store anything, just report")
    p.set_defaults(run=build_dataset)

    p = sub.add_parser("oi-levels", help="open-interest levels (walls, max pain, GEX) from a day's CBOE chain")
    p.add_argument("--date", type=date.fromisoformat, required=True, help="snapshot date, e.g. 2026-10-06")
    p.add_argument("--expiry", type=date.fromisoformat,
                   help="default: this week's last session if still ahead, else next week's")
    p.add_argument("--database-url", default=get_settings().DATABASE_URL)
    p.set_defaults(run=oi_levels)

    p = sub.add_parser("evaluate", help="walk-forward evaluation of the baselines; writes a report")
    p.add_argument("--database-url", default=get_settings().DATABASE_URL)
    p.add_argument("--first-test-year", type=int, default=2014)
    p.add_argument("--out", help="report folder (default: data/ml/reports at the repo root)")
    p.set_defaults(run=evaluate)
    args = parser.parse_args(argv)
    args.run(args)


if __name__ == "__main__":
    main()
