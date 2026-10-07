"""Which feature groups earn their place? Forward selection on the development years.

Start from the VIX group (what the baselines already know). At each step, try adding each remaining group,
keep the one that lowers the development pinball loss the most, and stop when no group improves it by at
least MIN_GAIN (relative). Every score is a full walk-forward over the development years, so a group only
survives if it helps out of sample.

Selection itself is a choice made by looking at the development years: the chosen set still has to prove
itself on the holdout.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Sequence

import numpy as np

from ..evaluation import walkforward
from ..evaluation.metrics import pinball

MIN_GAIN = 0.005    # half a percent


def dev_pinball(data, ctx, forecaster, years) -> float:
    preds = walkforward.run(data, ctx, [forecaster], years).dropna(subset=walkforward.QCOLS)
    y, q = walkforward.forecasts(preds)
    return pinball(y, q)


def forward_selection(data, ctx, make: Callable[[Sequence[str]], object], candidates: Sequence[str], years,
                      start: Sequence[str] = ("vix",), min_gain: float = MIN_GAIN,
                      log: Callable[[str], None] = print) -> List[Dict]:
    chosen = list(start)
    best = dev_pinball(data, ctx, make(chosen), years)
    steps = [{"groups": list(chosen), "added": None, "pinball": best, "tried": {}}]
    log(f"start {chosen}: pinball {best * 100:.4f}")
    remaining = [g for g in candidates if g not in chosen]
    while remaining:
        tried = {g: dev_pinball(data, ctx, make(chosen + [g]), years) for g in remaining}
        for g, score in sorted(tried.items(), key=lambda kv: kv[1]):
            log(f"  + {g:20} {score * 100:.4f}  ({(score / best - 1) * 100:+.2f}%)")
        group, score = min(tried.items(), key=lambda kv: kv[1])
        if score > best * (1 - min_gain):
            steps.append({"groups": list(chosen), "added": None, "pinball": best, "tried": tried, "stopped": True})
            log(f"stop: best addition {group} gains {(1 - score / best) * 100:.2f}% < {min_gain * 100:.1f}%")
            break
        chosen.append(group)
        remaining.remove(group)
        best = score
        steps.append({"groups": list(chosen), "added": group, "pinball": score, "tried": tried})
        log(f"keep {group}: pinball {score * 100:.4f}")
    return steps


def chosen_groups(steps: List[Dict]) -> List[str]:
    return list(steps[-1]["groups"]) if steps else []


def relative_path(steps: List[Dict]) -> List[float]:
    first = steps[0]["pinball"]
    return [float(np.round(s["pinball"] / first - 1, 6)) for s in steps]
