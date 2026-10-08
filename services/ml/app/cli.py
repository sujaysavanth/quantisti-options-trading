"""Command line for the ML service.

    python -m app.cli build-dataset                                # build all weeks, store them, print a report
    python -m app.cli build-dataset --export ../../data/ml/weekly.csv
    python -m app.cli build-dataset --no-write                     # report only, change nothing
    python -m app.cli evaluate                                     # baselines, walk-forward -> data/ml/reports/
    python -m app.cli evaluate --models                            # + models, development years 2014-2020 only
    python -m app.cli ablate --model gbm_sigma                     # which feature groups help (development years)
    python -m app.cli freeze --model gbm_quantile --groups vix,vix_term --conformal --reason "..."
    python -m app.cli holdout                                      # the frozen choice on 2021 on, once
    python -m app.cli backfill-forecasts                           # 2021+ forecasts as monitoring history
    python -m app.cli refresh-forecasts                            # forecast any new week now
    python -m app.cli explain-backfill                             # explanations for live forecasts made before ML-6

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
    from .tracking import data_dir
    return data_dir() / "reports"


def _load(args):
    from .forecasting import experiments
    with psycopg2.connect(args.database_url) as conn:
        data, ctx = experiments.load(conn)
    print(f"{len(data)} weeks ({data['anchor_date'].min()} .. {data['anchor_date'].max()}), "
          f"ATM straddle found for {len(ctx.straddle_sigma)} weeks")
    return data, ctx


def _out(args) -> Path:
    return Path(args.out) if getattr(args, "out", None) else default_reports_dir()


def _print_significance(summary) -> None:
    for name, by_ref in summary.get("significance", {}).items():
        cells = "  ".join(f"vs {ref}: {t['relative'] * 100:+.1f}% (p={t['p_value']:.3f})" for ref, t in by_ref.items()
                          if t.get("n"))
        print(f"  {name:28} {cells}")


def evaluate(args) -> None:
    from .evaluation import report, walkforward
    from .evaluation.baselines import all_baselines
    from .forecasting import experiments

    from . import tracking

    data, ctx = _load(args)
    if args.models:
        groups = args.groups.split(",") if args.groups else None
        params = {"period": "development", "groups": groups or "all", "research": args.research}
        with tracking.run("evaluate-models", params, data) as mlf:
            _, summary = experiments.development(data, ctx, groups=groups, research=args.research)
            stem = "models_dev" + ("_" + "_".join(groups) if groups else "") + ("_research" if args.research else "")
            paths = report.write(summary, _out(args), stem=stem, title="Models vs baselines: development years",
                                 intro=f"Models use feature groups: {', '.join(summary['groups'])}. Best baseline on "
                                       f"these years: {summary['best_baseline']}. The holdout years (2021 on) are not "
                                       "in this report; they are scored once, after `freeze`.")
            tracking.log_summary(mlf, summary)
            tracking.log_files(mlf, paths)
        print("\n".join(report.table(summary["overall"])))
        print(f"\nbest baseline: {summary['best_baseline']}; significance (one-sided Diebold-Mariano):")
        _print_significance(summary)
    else:
        baselines = all_baselines()
        last_year = max(a.year for a in data["anchor_date"])
        with tracking.run("evaluate-baselines", {"first_test_year": args.first_test_year}, data) as mlf:
            preds = walkforward.run(data, ctx, baselines, range(args.first_test_year, last_year + 1))
            summary = report.summarize(preds, [b.name for b in baselines])
            paths = report.write(summary, _out(args))
            tracking.log_summary(mlf, summary)
            tracking.log_files(mlf, paths)
        print("\n".join(report.table(summary["overall"])))
    print("\nwritten: " + ", ".join(str(p) for p in paths))


def ablate(args) -> None:
    import json

    from .forecasting import ablation, experiments

    from . import tracking

    data, ctx = _load(args)
    with tracking.run("ablate", {"model": args.model, "period": "development"}, data) as mlf:
        steps = experiments.run_ablation(data, ctx, model=args.model)
        out = _out(args)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"ablation_{args.model}.json"
        path.write_text(json.dumps({"model": args.model, "steps": steps}, indent=2, default=str), encoding="utf8")
        if mlf:
            mlf.log_param("kept_groups", ",".join(ablation.chosen_groups(steps)))
            for i, step in enumerate(steps):
                mlf.log_metric("pinball", float(step["pinball"]), step=i)
            tracking.log_files(mlf, [path])
    print(f"\nkept groups for {args.model}: {', '.join(ablation.chosen_groups(steps))}")
    print(f"written: {path}")


def freeze(args) -> None:
    from . import tracking
    from .evaluation import periods
    from .forecasting import experiments

    choice = {"model": args.model, "groups": args.groups.split(","), "conformal": args.conformal,
              "reference": args.reference, "reason": args.reason}
    data, ctx = _load(args)
    name = experiments.chosen_name(choice)
    with tracking.run("freeze", {**choice, "period": "development"}, data) as mlf:
        dev_preds, dev = experiments.score_choice(data, ctx, choice, periods.DEV_YEARS, args.reference)
        choice["development"] = {"overall": dev["overall"][name], "significance": dev["significance"].get(name)}
        tracking.log_summary(mlf, dev)
        if mlf:
            from .registry import register
            forecaster, adjustments, train = experiments.fit_for_registry(data, ctx, choice, dev_preds)
            example = train.drop(columns=[c for c in ("close_ret", "high_ret", "low_ret", "sessions", "next_anchor_date")
                                          if c in train.columns]).tail(3)
            choice["registered_version"] = register(mlf, forecaster, choice, adjustments, example)
            choice["mlflow_run_id"] = mlf.active_run().info.run_id
        record = periods.freeze(choice)
    print(f"frozen {name} on {', '.join(choice['groups'])} at {record['frozen_at']}: "
          f"dev pinball {dev['overall'][name]['pinball'] * 100:.3f}, 80% hit {dev['overall'][name]['coverage_80']:.1%}"
          + (f"; registered as {tracking.REGISTERED_MODEL} v{choice['registered_version']}"
             if choice.get("registered_version") else ""))
    print(f"written: {periods.CHOICE_FILE}")


def holdout(args) -> None:
    from . import tracking
    from .evaluation import periods, report
    from .forecasting import experiments

    choice = periods.holdout_allowed(force=args.force)
    data, ctx = _load(args)
    years = periods.holdout_years(max(a.year for a in data["anchor_date"]))
    name = experiments.chosen_name(choice)
    print(f"holdout {years.start}-{years.stop - 1}, frozen choice: {name} on {', '.join(choice['groups'])}")
    params = {"model": name, "groups": choice["groups"], "period": "holdout", "forced_rerun": args.force}
    with tracking.run("holdout", params, data) as mlf:
        _, summary = experiments.score_choice(data, ctx, choice, years, choice.get("reference"))
        paths = report.write(summary, _out(args), stem="holdout", title="Holdout: the frozen choice, scored once",
                             intro=f"Frozen choice: {name} on {', '.join(choice['groups'])} "
                                   f"(frozen {choice['frozen_at']}).")
        tracking.log_summary(mlf, summary)
        tracking.log_files(mlf, paths)
    periods.record_holdout({"overall": summary["overall"], "significance": summary["significance"]})
    print("\n".join(report.table(summary["overall"])))
    _print_significance(summary)
    print("\nwritten: " + ", ".join(str(p) for p in paths) + f", {periods.CHOICE_FILE}")


def backfill_forecasts(args) -> None:
    from .forecasting import serving
    with psycopg2.connect(args.database_url) as conn:
        n = serving.backfill(conn)
    print(f"stored {n} backfilled forecasts (2021 on, walk-forward with yearly refits, origin 'backfill')")


def refresh_forecasts(args) -> None:
    from .forecasting import serving
    with psycopg2.connect(args.database_url) as conn:
        result = serving.refresh(conn, log_fn=print)
    print(result)


def explain_backfill(args) -> None:
    from .forecasting import serving
    with psycopg2.connect(args.database_url) as conn:
        n = serving.explain_missing(conn)
    print(f"added {n} explanations to live forecasts that had none")


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

    db = {"default": get_settings().DATABASE_URL}
    p = sub.add_parser("evaluate", help="walk-forward evaluation; writes a report")
    p.add_argument("--database-url", **db)
    p.add_argument("--models", action="store_true", help="baselines + models on the development years (2014-2020)")
    p.add_argument("--groups", help="with --models: feature groups for the models, e.g. vix,options,vix_term")
    p.add_argument("--research", action="store_true", help="with --models: add Chronos-2 (needs .[research])")
    p.add_argument("--first-test-year", type=int, default=2014, help="baselines only: first test year")
    p.add_argument("--out", help="report folder (default: data/ml/reports at the repo root)")
    p.set_defaults(run=evaluate)

    p = sub.add_parser("ablate", help="forward feature-group selection on the development years")
    p.add_argument("--database-url", **db)
    p.add_argument("--model", default="gbm_sigma", choices=["ridge_sigma", "gbm_sigma", "ebm_sigma", "gbm_quantile"])
    p.add_argument("--out")
    p.set_defaults(run=ablate)

    p = sub.add_parser("freeze", help="record the development-period choice before the holdout")
    p.add_argument("--database-url", **db)
    p.add_argument("--model", required=True, choices=["ridge_sigma", "gbm_sigma", "ebm_sigma", "gbm_quantile", "chronos2", "chronos2_cov", "vix_scaled"])
    p.add_argument("--groups", required=True, help="comma-separated feature groups, e.g. vix,vix_term,options")
    p.add_argument("--conformal", action="store_true", help="add per-regime conformal calibration")
    p.add_argument("--reference", default="vix_scaled", help="baseline to beat, e.g. garch+conformal")
    p.add_argument("--reason", default="", help="one line on why (recorded)")
    p.set_defaults(run=freeze)

    p = sub.add_parser("backfill-forecasts", help="store the 2021+ walk-forward forecasts as monitoring history")
    p.add_argument("--database-url", **db)
    p.set_defaults(run=backfill_forecasts)

    p = sub.add_parser("refresh-forecasts", help="rebuild the dataset and forecast any new week (as the scheduler does)")
    p.add_argument("--database-url", **db)
    p.set_defaults(run=refresh_forecasts)

    p = sub.add_parser("explain-backfill", help="add explanations to live forecasts stored before ML-6")
    p.add_argument("--database-url", **db)
    p.set_defaults(run=explain_backfill)

    p = sub.add_parser("holdout", help="score the frozen choice on 2021 onwards, once")
    p.add_argument("--database-url", **db)
    p.add_argument("--force", action="store_true", help="run again although it has run (the re-run is recorded)")
    p.add_argument("--out")
    p.set_defaults(run=holdout)
    args = parser.parse_args(argv)
    args.run(args)


if __name__ == "__main__":
    main()
