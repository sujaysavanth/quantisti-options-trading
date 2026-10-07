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
from pathlib import Path

import numpy as np
import psycopg2

from .config import get_settings
from .dataset import store
from .dataset.features import MODEL_FEATURES

Z80 = 1.2816   # 10% / 90% quantiles of a standard normal


def report(features, labels) -> None:
    complete = features.dropna(subset=list(MODEL_FEATURES))
    data = complete.merge(labels, on="anchor_date")
    print(f"weeks: {len(features)} ({features['anchor_date'].min()} .. {features['anchor_date'].max()}), "
          f"with all features: {len(complete)} (from {complete['anchor_date'].min()}), "
          f"usable for training (features + label): {len(data)}")
    if data.empty:
        return
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
        if not args.no_write:
            n_features, n_labels = store.save(conn, features, labels)
            print(f"stored {n_features} weeks of features and {n_labels} labels")
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
    """Weeks with every model feature and a label: what forecasters are fitted and scored on."""
    return features.dropna(subset=list(MODEL_FEATURES)).merge(labels, on="anchor_date")


def evaluate(args) -> None:
    from .evaluation import report, walkforward
    from .evaluation.baselines import Context, all_baselines, straddle_sigma

    with psycopg2.connect(args.database_url) as conn:
        features, labels = store.build(conn)
        daily, _, _ = store.load_market(conn)
        data = training_rows(features, labels)
        pairs = [(a, n) for a, n in zip(data["anchor_date"], data["next_anchor_date"]) if a.year <= 2023]
        quotes = store.load_straddle_quotes(conn, pairs)
    ctx = Context(daily[["date", "close"]], straddle_sigma(quotes))
    print(f"{len(data)} weeks ({data['anchor_date'].min()} .. {data['anchor_date'].max()}), "
          f"ATM straddle found for {len(ctx.straddle_sigma)} of {len(pairs)} weeks up to 2023")

    baselines = all_baselines()
    last_year = max(a.year for a in data["anchor_date"])
    preds = walkforward.run(data, ctx, baselines, range(args.first_test_year, last_year + 1))
    summary = report.summarize(preds, [b.name for b in baselines])
    paths = report.write(summary, Path(args.out) if args.out else default_reports_dir())
    print("\n".join(report.table(summary["overall"])))
    print("\nwritten: " + ", ".join(str(p) for p in paths))


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build-dataset", help="weekly features + next-week labels for every complete week")
    p.add_argument("--database-url", default=get_settings().DATABASE_URL)
    p.add_argument("--export", help="also write features + labels to this CSV (data/ is git-ignored)")
    p.add_argument("--no-write", action="store_true", help="don't store anything, just report")
    p.set_defaults(run=build_dataset)

    p = sub.add_parser("evaluate", help="walk-forward evaluation of the baselines; writes a report")
    p.add_argument("--database-url", default=get_settings().DATABASE_URL)
    p.add_argument("--first-test-year", type=int, default=2014)
    p.add_argument("--out", help="report folder (default: data/ml/reports at the repo root)")
    p.set_defaults(run=evaluate)
    args = parser.parse_args(argv)
    args.run(args)


if __name__ == "__main__":
    main()
