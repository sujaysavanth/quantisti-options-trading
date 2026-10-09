"""Forecasts of SPX's close at any of the next H_MAX sessions: one range per listed expiry, not just next week's.

GARCH(1,1) forecasts variance for any number of days ahead. From the close of day t, with p = alpha + beta and
long-run daily variance LR = omega / (1 - p), day k ahead has variance

    v_k = LR + p^(k-1) * (v_1 - LR),        v_1 = tomorrow's variance, known at t's close

and the close h sessions ahead has sigma_h = sqrt(v_1 + ... + v_h). As with the weekly forecasts, sigma_h becomes
quantiles through empirical multipliers z_h (the 5/10/50/90/95% quantiles of return_h / sigma_h over the
training days), learned separately for each horizon: one day is fatter-tailed than five.

Validation (evaluate-horizons): walk-forward over 2014-2020, refitted at the start of each year, every session an
origin, horizons 1..H_MAX; calibrated VIX at the same horizon is the yardstick. A horizon is shown only if its
80% band held between GATE[0] and GATE[1] of the time. The result is frozen in services/ml/horizons.json and the
holdout years (2021 on) are scored once, as for the weekly model (periods.py).

Live (serving): at each session's close GARCH is refitted on every return so far and every listed expiry within
H_MAX sessions gets a forecast with its per-day variance path, so a page can remove the part of today that has
already traded. Forecasts are stored once (expiry_forecasts).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from .. import market_spec
from ..evaluation.baselines import TRADING_DAYS, Context, Garch
from ..evaluation.metrics import QUANTILES, REGIMES, pinball, regime_of
from ..evaluation.walkforward import QCOLS

H_MAX = 10
HORIZONS = range(1, H_MAX + 1)
GATE = (0.75, 0.85)
WARMUP = 22                       # sessions before the first training origin (the filter settles)
HORIZONS_FILE = Path(__file__).resolve().parents[2] / "horizons.json"      # services/ml/horizons.json


@dataclass
class HorizonData:
    """Daily closes and VIX on one calendar, oldest first."""
    ctx: Context
    dates: np.ndarray             # datetime64 per session
    log_close: np.ndarray
    vix: np.ndarray               # VIX close on the same day (carried forward over gaps)

    @classmethod
    def from_frames(cls, daily: pd.DataFrame, vix: pd.DataFrame) -> "HorizonData":
        d = daily[["date", "close"]].sort_values("date").reset_index(drop=True)
        v = d[["date"]].merge(vix.rename(columns={"close": "vix"}), on="date", how="left")["vix"].ffill()
        return cls(Context(d), pd.to_datetime(d["date"]).to_numpy(), np.log(d["close"].astype(float).to_numpy()),
                   v.astype(float).to_numpy())

    def index_of(self, day) -> int:
        return int(np.searchsorted(self.dates, np.datetime64(pd.Timestamp(day))))

    def day(self, i: int) -> date:
        return pd.Timestamp(self.dates[i]).date()

    def returns(self, h: int) -> np.ndarray:
        """ln(close[i + h] / close[i]) for every origin i; NaN where i + h is past the data."""
        out = np.full(len(self.log_close), np.nan)
        out[: len(out) - h] = self.log_close[h:] - self.log_close[:-h]
        return out


def fit_garch(data: HorizonData, cutoff_day) -> Garch:
    """GARCH(1,1) on every return up to `cutoff_day`'s close; its filter then runs over all days with those
    parameters (a day's variance forecast uses returns up to that day only)."""
    g = Garch()
    g.fit_sigma(pd.DataFrame({"next_anchor_date": [pd.Timestamp(cutoff_day)]}), data.ctx)
    return g


def variance_paths(g: Garch, h_max: int = H_MAX) -> np.ndarray:
    """(sessions, h_max): variance of each of the next h_max days from each close, as a fraction squared."""
    v1 = g.h_next[:, None]
    p = g.alpha + g.beta_
    k = np.arange(h_max)[None, :]
    if p >= 0.9999:
        path = np.repeat(v1, h_max, axis=1)
    else:
        lr = g.omega / (1 - p)
        path = lr + p ** k * (v1 - lr)
    return path / 1e4


def sigmas(paths: np.ndarray) -> np.ndarray:
    """(sessions, h_max): sigma_h of the close h sessions ahead."""
    return np.sqrt(np.clip(np.cumsum(paths, axis=1), 1e-16, None))


def vix_sigmas(data: HorizonData, h_max: int = H_MAX) -> np.ndarray:
    return data.vix[:, None] / 100 * np.sqrt(np.arange(1, h_max + 1)[None, :] / TRADING_DAYS)


def z_multipliers(sig: np.ndarray, data: HorizonData, last_origin_label: int) -> np.ndarray:
    """(h_max, 5): empirical quantiles of return_h / sigma_h over origins whose outcome is known by
    session `last_origin_label` (i + h <= last_origin_label)."""
    z = np.full((sig.shape[1], len(QUANTILES)), np.nan)
    for h in range(1, sig.shape[1] + 1):
        y = data.returns(h)
        idx = np.arange(WARMUP, max(last_origin_label - h + 1, WARMUP))
        ratio = y[idx] / sig[idx, h - 1]
        ratio = ratio[np.isfinite(ratio)]
        if len(ratio) >= 100:
            z[h - 1] = np.quantile(ratio, QUANTILES)
    return z


def walk_forward(data: HorizonData, years: Iterable[int], h_max: int = H_MAX,
                 log: Callable[[str], None] = lambda _: None) -> pd.DataFrame:
    """For each year Y: fit on everything before Y, forecast every session of Y at every horizon.
    Long format: origin_date, year, horizon, method (garch | vix_scaled), vix_close, y, q05..q95."""
    years_of = pd.to_datetime(pd.Series(data.dates)).dt.year.to_numpy()
    vsig_all = vix_sigmas(data, h_max)
    frames = []
    for year in years:
        test = np.flatnonzero(years_of == year)
        if not len(test) or test[0] <= WARMUP + 250:
            continue
        cutoff = test[0] - 1
        g = fit_garch(data, data.day(cutoff))
        gsig = sigmas(variance_paths(g, h_max))
        for method, sig in (("garch", gsig), ("vix_scaled", vsig_all)):
            z = z_multipliers(sig, data, cutoff)
            for h in range(1, h_max + 1):
                y = data.returns(h)[test]
                q = sig[test, h - 1][:, None] * z[h - 1][None, :]
                frames.append(pd.DataFrame({
                    "origin_date": [data.day(i) for i in test], "year": year, "horizon": h, "method": method,
                    "vix_close": data.vix[test], "y": y, **{c: q[:, j] for j, c in enumerate(QCOLS)}}))
        log(f"  {year}: fitted through {data.day(cutoff)}, {len(test)} origins x {h_max} horizons")
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return out.dropna(subset=["y", *QCOLS]) if len(out) else out


def horizon_stats(g: pd.DataFrame) -> Dict:
    y, q = g["y"].to_numpy(float), g[QCOLS].to_numpy(float)
    in80 = (y >= q[:, 1]) & (y <= q[:, 3])
    in90 = (y >= q[:, 0]) & (y <= q[:, 4])
    regimes = regime_of(g["vix_close"].to_numpy(float))
    return {
        "origins": int(len(y)), "coverage_80": float(in80.mean()), "coverage_90": float(in90.mean()),
        "width_80": float(np.mean(q[:, 3] - q[:, 1])), "pinball": pinball(y, q),
        "coverage_80_by_regime": {name: {"origins": int((regimes == name).sum()),
                                         "coverage_80": float(in80[regimes == name].mean()) if (regimes == name).any() else None}
                                  for name, _, _ in REGIMES},
    }


def evaluate(preds: pd.DataFrame, gate=GATE) -> Dict[str, Dict]:
    """Per horizon: GARCH's stats, calibrated VIX's for comparison, and whether GARCH passes the gate."""
    out = {}
    for h, g in preds.groupby("horizon"):
        garch = horizon_stats(g[g["method"] == "garch"])
        vix = horizon_stats(g[g["method"] == "vix_scaled"])
        out[str(int(h))] = {**garch, "vix_scaled": {k: vix[k] for k in ("coverage_80", "coverage_90", "width_80", "pinball")},
                            "valid": bool(gate[0] <= garch["coverage_80"] <= gate[1])}
    return out


def report(result: Dict[str, Dict], title: str) -> str:
    lines = [f"# {title}", "", "| h | origins | cover 80 | cover 90 | width 80 | pinball x100 | VIX-scaled pinball x100 | calm / normal / stressed 80 | shown |",
             "|---|---|---|---|---|---|---|---|---|"]
    for h, r in sorted(result.items(), key=lambda kv: int(kv[0])):
        reg = " / ".join("-" if v["coverage_80"] is None else f"{v['coverage_80']:.0%}" for v in r["coverage_80_by_regime"].values())
        lines.append(f"| {h} | {r['origins']} | {r['coverage_80']:.1%} | {r['coverage_90']:.1%} | {r['width_80'] * 100:.2f}% | "
                     f"{r['pinball'] * 100:.3f} | {r['vix_scaled']['pinball'] * 100:.3f} | {reg} | {'yes' if r.get('valid', True) else 'NO'} |")
    return "\n".join(lines) + "\n"


# --- the record (services/ml/horizons.json) ---------------------------------------------------------------

def load_record(path: Path = HORIZONS_FILE) -> Optional[Dict]:
    return json.loads(path.read_text(encoding="utf8")) if path.exists() else None


def freeze(result: Dict, years: Iterable[int], path: Path = HORIZONS_FILE) -> Dict:
    existing = load_record(path)
    if existing and existing.get("holdout"):
        raise RuntimeError(f"{path} already has a holdout result; re-deciding the gate now would use hindsight")
    years = list(years)
    record = {"method": "garch", "dev_years": [years[0], years[-1]], "gate_coverage_80": list(GATE),
              "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "horizons": result, "holdout": None}
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf8")
    return record


def record_holdout(result: Dict, years: Iterable[int], force: bool = False, path: Path = HORIZONS_FILE) -> Dict:
    record = load_record(path)
    if record is None:
        raise RuntimeError("no frozen horizons: run `python -m app.cli evaluate-horizons --freeze` first")
    if record.get("holdout") and not force:
        raise RuntimeError("the horizons holdout has already been scored (use --force to re-run; it is recorded)")
    years = list(years)
    entry = {"years": [years[0], years[-1]], "horizons": result, "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if record.get("holdout"):
        record.setdefault("holdout_reruns", []).append(entry)
    else:
        record["holdout"] = entry
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf8")
    return record


def validation(h: int, record: Optional[Dict]) -> Dict:
    """Is horizon h shown, and why (from the frozen development result)."""
    r = ((record or {}).get("horizons") or {}).get(str(h))
    if r is None:
        return {"valid": False, "reason": "not validated (run evaluate-horizons --freeze)"}
    cov = r["coverage_80"]
    reason = (f"80% band held {cov:.0%} of the time in {record['dev_years'][0]}-{record['dev_years'][1]}"
              + ("" if r["valid"] else f", outside {GATE[0]:.0%}-{GATE[1]:.0%}"))
    return {"valid": bool(r["valid"]), "reason": reason, "dev_coverage_80": cov}


# --- live forecasts ------------------------------------------------------------------------------------------

def listed_expiries(origin: date, h_max: int = H_MAX) -> List[tuple]:
    """(expiry, sessions ahead, the sessions up to it) for listed expiries within h_max sessions of `origin`."""
    sessions = market_spec.trading_days(origin + timedelta(days=1), origin + timedelta(days=7 * (h_max // 5 + 2)))[:h_max]
    return [(d, k + 1, sessions[: k + 1]) for k, d in enumerate(sessions) if market_spec.is_expiry(d)]


def forecast_origin(data: HorizonData, origin_day, origin: str = "live") -> pd.DataFrame:
    """Every listed expiry within H_MAX sessions, from `origin_day`'s close, fitted on data up to that close."""
    i = data.index_of(origin_day)
    if i >= len(data.dates) or data.day(i) != pd.Timestamp(origin_day).date():
        raise ValueError(f"{origin_day} is not a session in the data")
    g = fit_garch(data, data.day(i))
    paths = variance_paths(g)
    sig = sigmas(paths)
    z = z_multipliers(sig, data, i)
    rows = []
    for expiry, h, sessions in listed_expiries(data.day(i)):
        q = sig[i, h - 1] * z[h - 1]
        rows.append({"origin_date": data.day(i), "expiry_date": expiry, "sessions": h, "method": "garch", "origin": origin,
                     "spot": float(np.exp(data.log_close[i])), "vix_close": float(data.vix[i]),
                     **dict(zip(QCOLS, q)), "sigma": float(sig[i, h - 1]), "z": [float(v) for v in z[h - 1]],
                     "variance_path": [float(v) for v in paths[i, :h]], "path_dates": list(sessions),
                     "trained_through": data.day(i)})
    return pd.DataFrame(rows)


def backfill_frame(data: HorizonData, preds: pd.DataFrame) -> pd.DataFrame:
    """Walk-forward GARCH predictions turned into stored rows, for origin/expiry pairs that were listed."""
    g = preds[preds["method"] == "garch"]
    keep = []
    for origin_day, rows in g.groupby("origin_date"):
        listed = {h: (e, s) for e, h, s in listed_expiries(origin_day)}
        for _, r in rows[rows["horizon"].isin(listed)].iterrows():
            e, s = listed[int(r["horizon"])]
            q = r[QCOLS].to_numpy(float)
            keep.append({"origin_date": origin_day, "expiry_date": e, "sessions": int(r["horizon"]), "method": "garch",
                         "origin": "backfill", "spot": float(np.exp(data.log_close[data.index_of(origin_day)])),
                         "vix_close": float(r["vix_close"]), **dict(zip(QCOLS, q)), "sigma": None, "z": None,
                         "variance_path": None, "path_dates": list(s), "trained_through": None})
    return pd.DataFrame(keep)
