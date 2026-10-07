"""Turn walk-forward forecasts into a summary (JSON) and a readable report (markdown)."""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Dict, List

import pandas as pd

from .metrics import score
from .walkforward import forecasts

REGIMES = (("calm (VIX < 15)", 0, 15), ("normal (VIX 15-25)", 15, 25), ("stressed (VIX >= 25)", 25, math.inf))


def summarize(preds: pd.DataFrame, order: List[str]) -> Dict:
    names = [n for n in order if n in set(preds["forecaster"])]
    groups = {n: preds[preds["forecaster"] == n] for n in names}
    straddle = groups.get("straddle")
    straddle_weeks = set(straddle.dropna()["anchor_date"]) if straddle is not None else set()

    def scored(filter_fn) -> Dict:
        return {n: score(*forecasts(filter_fn(g))) for n, g in groups.items()}

    return {
        "generated": date.today().isoformat(),
        "test_years": sorted(int(y) for y in preds["year"].unique()),
        "overall": scored(lambda g: g),
        "straddle_weeks": scored(lambda g: g[g["anchor_date"].isin(straddle_weeks)]),
        "by_year": {int(y): {n: score(*forecasts(g[g["year"] == y])) for n, g in groups.items()}
                    for y in sorted(preds["year"].unique())},
        "by_regime": {label: scored(lambda g, lo=lo, hi=hi: g[(g["vix_close"] >= lo) & (g["vix_close"] < hi)])
                      for label, lo, hi in REGIMES},
    }


def _pct(x, digits=2):
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x * 100:.{digits}f}"


def table(scores: Dict) -> List[str]:
    lines = ["| forecaster | weeks | 80% band hit | 90% band hit | 80% band width | pinball | Winkler (80%) |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for name, s in scores.items():
        if not s.get("n"):
            lines.append(f"| {name} | 0 | | | | | |")
            continue
        lines.append(f"| {name} | {s['n']} | {_pct(s['coverage_80'], 1)}% | {_pct(s['coverage_90'], 1)}% | "
                     f"{_pct(s['width_80'])}% | {_pct(s['pinball'], 3)} | {_pct(s['winkler_80'])} |")
    return lines


def to_markdown(summary: Dict) -> str:
    years = summary["test_years"]
    out = [
        "# Baselines: next-week SPX close, walk-forward",
        "",
        f"Generated {summary['generated']}. Test years {years[0]}-{years[-1]}: each year is forecast by a model fitted "
        "only on the years before it. Returns are log returns from one week's last close to the next; widths, "
        "pinball and Winkler are in percent of the index (lower is better). A calibrated forecaster hits the 80% "
        "band about 80% of the time; more means its range is too wide, less means too narrow.",
        "",
        "## All test weeks",
        "",
        *table(summary["overall"]),
        "",
        "## Weeks with a real ATM straddle (2014-2023)",
        "",
        "Every forecaster scored on the same weeks, so the option-implied baseline is compared fairly.",
        "",
        *table(summary["straddle_weeks"]),
        "",
        "## Coverage of the 80% band by VIX regime",
        "",
        "Hitting 80% overall can hide a range that is too wide in calm weeks and too narrow in stressed ones.",
        "",
    ]
    names = list(summary["overall"])
    out += ["| regime | weeks | " + " | ".join(names) + " |", "|---|---:|" + "---:|" * len(names)]
    for regime, scores in summary["by_regime"].items():
        n = max((s.get("n", 0) for s in scores.values()), default=0)
        out.append(f"| {regime} | {n} | " + " | ".join(
            f"{_pct(s.get('coverage_80'), 0)}%" if s.get("n") else "-" for s in scores.values()) + " |")
    out += ["", "## Pinball loss by year", "", "| year | " + " | ".join(names) + " |", "|---|" + "---:|" * len(names)]
    for year, scores in summary["by_year"].items():
        out.append(f"| {year} | " + " | ".join(_pct(s.get("pinball"), 3) if s.get("n") else "-" for s in scores.values()) + " |")
    return "\n".join(out) + "\n"


def write(summary: Dict, out_dir: Path, stem: str = "baselines") -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, md_path = out_dir / f"{stem}.json", out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf8")
    md_path.write_text(to_markdown(summary), encoding="utf8")
    return [json_path, md_path]
