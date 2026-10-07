"""Turn walk-forward forecasts into a summary (JSON) and a readable report (markdown)."""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Dict, List

import pandas as pd

from .metrics import REGIMES, score
from .walkforward import QCOLS, forecasts


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


def significance(preds: pd.DataFrame, names: List[str], references: List[str]) -> Dict:
    """Diebold-Mariano of each forecaster against each reference, on the weeks both have."""
    from .metrics import pinball_rows
    from .significance import diebold_mariano

    loss = {}
    for n in set(names) | set(references):
        g = preds[preds["forecaster"] == n].dropna(subset=QCOLS)
        y, q = forecasts(g)
        loss[n] = pd.Series(pinball_rows(y, q), index=g["anchor_date"].to_numpy())
    out = {}
    for n in names:
        for ref in references:
            if n == ref or n not in loss or ref not in loss:
                continue
            both = loss[n].index.intersection(loss[ref].index)
            out.setdefault(n, {})[ref] = diebold_mariano(loss[n][both].to_numpy(), loss[ref][both].to_numpy())
    return out


def _p(x):
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.3f}"


def to_markdown(summary: Dict, title: str = "Baselines: next-week SPX close, walk-forward", intro: str = "") -> str:
    years = summary["test_years"]
    out = [
        f"# {title}",
        "",
        f"Generated {summary['generated']}. Test years {years[0]}-{years[-1]}: each year is forecast by a model fitted "
        "only on the years before it. Returns are log returns from one week's last close to the next; widths, "
        "pinball and Winkler are in percent of the index (lower is better). A calibrated forecaster hits the 80% "
        "band about 80% of the time; more means its range is too wide, less means too narrow.",
        *(["", intro] if intro else []),
        "",
        "## All test weeks",
        "",
        *table(summary["overall"]),
    ]
    if summary.get("straddle_weeks") and any(s.get("n") for s in summary["straddle_weeks"].values()):
        out += ["", "## Weeks with a real ATM straddle", "",
                "Every forecaster scored on the same weeks, so the option-implied baseline is compared fairly.", "",
                *table(summary["straddle_weeks"])]
    if summary.get("significance"):
        refs = sorted({r for v in summary["significance"].values() for r in v})
        out += ["", "## Is it really better? (Diebold-Mariano, one-sided)", "",
                "Change in pinball loss against each reference (negative = better) and the p-value: the chance of a "
                "gap this large if the forecaster were really no better. Below 0.05 is the usual bar.", "",
                "| forecaster | " + " | ".join(f"vs {r}: change | p" for r in refs) + " |",
                "|---|" + "---:|---:|" * len(refs)]
        for name, by_ref in summary["significance"].items():
            cells = []
            for r in refs:
                t = by_ref.get(r)
                cells.append(f"{t['relative'] * 100:+.1f}% | {_p(t['p_value'])}" if t else "- | -")
            out.append(f"| {name} | " + " | ".join(cells) + " |")
    regimes = list(summary["by_regime"])
    out += ["", "## Coverage of the 80% band by VIX regime", "",
            "Hitting 80% overall can hide a range that is too wide in calm weeks and too narrow in stressed ones.", "",
            "| forecaster | " + " | ".join(f"{r} ({max(s.get('n', 0) for s in summary['by_regime'][r].values())} wks)"
                                         for r in regimes) + " |",
            "|---|" + "---:|" * len(regimes)]
    for name in summary["overall"]:
        out.append(f"| {name} | " + " | ".join(
            f"{_pct(summary['by_regime'][r][name].get('coverage_80'), 0)}%" if summary["by_regime"][r][name].get("n")
            else "-" for r in regimes) + " |")
    years_ = list(summary["by_year"])
    out += ["", "## Pinball loss by year", "", "| forecaster | " + " | ".join(str(y) for y in years_) + " |",
            "|---|" + "---:|" * len(years_)]
    for name in summary["overall"]:
        out.append(f"| {name} | " + " | ".join(
            _pct(summary["by_year"][y][name].get("pinball"), 3) if summary["by_year"][y][name].get("n") else "-"
            for y in years_) + " |")
    return "\n".join(out) + "\n"


def write(summary: Dict, out_dir: Path, stem: str = "baselines", title: str = None, intro: str = "") -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, md_path = out_dir / f"{stem}.json", out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf8")
    kwargs = {"title": title} if title else {}
    md_path.write_text(to_markdown(summary, intro=intro, **kwargs), encoding="utf8")
    return [json_path, md_path]
