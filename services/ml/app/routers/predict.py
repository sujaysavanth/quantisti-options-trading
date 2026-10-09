"""Weekly range forecast endpoints.

    GET  /v1/predict/weekly       the latest week's stored forecast (or ?anchor=YYYY-MM-DD for an earlier one)
    GET  /v1/predict/expiries     every listed expiry within 10 sessions, from the latest close (?origin= earlier)
    GET  /v1/predict/monitoring   calibration of the stored forecasts over the last 26 and 52 weeks, with drift flags
    POST /v1/predict/refresh      rebuild the dataset and forecast any new week now (normally done after Friday's close)
"""

import logging
import math
from datetime import date
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from ..dataset import store
from ..evaluation.walkforward import QCOLS
from ..forecasting import horizons, monitoring, serving
from ..services.feature_service import SUPPORTED_SYMBOLS, _connection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/predict", tags=["predict"])
SCHEDULER = None            # set by main.py when the weekly refresh thread runs


def _check(symbol: str) -> None:
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Only {', '.join(SUPPORTED_SYMBOLS)} is supported")


def _block(r: pd.Series) -> dict:
    """One method's forecast: return quantiles, the same as index levels, and the 80% / 90% ranges."""
    spot = float(r["spot"])
    levels = {c: round(spot * math.exp(float(r[c])), 2) for c in QCOLS}
    return {
        "method": r["method"], "origin": r["origin"], "details": r["details"],
        "trained_through": str(r["trained_through"]) if r["trained_through"] is not None else None,
        "quantiles": {c: round(float(r[c]), 6) for c in QCOLS},
        "levels": levels,
        "median": levels["q50"],
        "range_80": [levels["q10"], levels["q90"]],
        "range_90": [levels["q05"], levels["q95"]],
        "explanation": r.get("explanation") if isinstance(r.get("explanation"), dict) else None,
    }


@router.get("/weekly", summary="Next week's SPX closing range")
def weekly(symbol: str = Query("SPX"), anchor: Optional[date] = Query(None, description="a past week's last session")):
    """Where SPX is likely to close at next week's expiry, made at the close of the week's last session.

    `served` is the forecast to use; `second_opinion` is the frozen model (better coverage in stressed weeks);
    `reference` is VIX as published. Once the week has closed, `outcome` shows where it actually closed.
    """
    _check(symbol)
    with _connection() as conn:
        if anchor is None:
            served = store.read_forecasts(conn, symbol)
            served = served[served["role"] == "served"]
            if served.empty:
                raise HTTPException(status_code=404, detail="No forecasts yet: POST /v1/predict/refresh")
            anchor = served["anchor_date"].max()
        rows = store.read_forecasts(conn, symbol, anchor)
    if rows.empty:
        raise HTTPException(status_code=404, detail=f"No forecast for the week ending {anchor}")
    by_role = {r["role"]: r for _, r in rows.iterrows()}
    first = rows.iloc[0]
    out = {"symbol": symbol, "anchor_date": str(first["anchor_date"]), "expiry_date": str(first["expiry_date"]),
           "spot": float(first["spot"]), "vix_close": first["vix_close"],
           **{role: _block(by_role[role]) for role in ("served", "second_opinion", "reference") if role in by_role}}
    if pd.notna(first["close_ret"]):
        close = float(first["spot"]) * math.exp(float(first["close_ret"]))
        out["outcome"] = {"close": round(close, 2), "close_ret": float(first["close_ret"]),
                          "inside_served_80": bool(out["served"]["range_80"][0] <= close <= out["served"]["range_80"][1])}
    return out


def _expiry_row(r: pd.Series, record) -> dict:
    spot = float(r["spot"])
    levels = {c: round(spot * math.exp(float(r[c])), 2) for c in QCOLS}
    out = {
        "expiry_date": str(r["expiry_date"]), "sessions": int(r["sessions"]), "method": r["method"], "origin": r["origin"],
        "quantiles": {c: round(float(r[c]), 6) for c in QCOLS}, "levels": levels,
        "range_80": [levels["q10"], levels["q90"]], "range_90": [levels["q05"], levels["q95"]],
        "sigma": None if r["sigma"] is None or pd.isna(r["sigma"]) else float(r["sigma"]),
        "z": list(r["z"]) if isinstance(r["z"], (list, tuple)) else None,
        "variance_path": list(r["variance_path"]) if isinstance(r["variance_path"], (list, tuple)) else None,
        "path_dates": [str(d) for d in r["path_dates"]] if isinstance(r["path_dates"], (list, tuple)) else None,
        "validation": horizons.validation(int(r["sessions"]), record),
    }
    if pd.notna(r["close_ret"]):
        close = spot * math.exp(float(r["close_ret"]))
        out["outcome"] = {"close": round(close, 2), "inside_80": bool(levels["q10"] <= close <= levels["q90"])}
    return out


@router.get("/expiries", summary="The close at every listed expiry within 10 sessions")
def expiries(symbol: str = Query("SPX"), origin: Optional[date] = Query(None, description="an earlier session close")):
    """GARCH forecasts made at a session's close for each listed expiry up to 10 sessions ahead, with the per-day
    variance path (to remove the part of today already traded) and whether that horizon passed validation."""
    _check(symbol)
    with _connection() as conn:
        if origin is None:
            have = store.expiry_origins(conn, symbol)
            if not have:
                raise HTTPException(status_code=404, detail="No expiry forecasts yet: POST /v1/predict/refresh")
            origin = max(have)
        rows = store.read_expiry_forecasts(conn, symbol, origin)
    if rows.empty:
        raise HTTPException(status_code=404, detail=f"No expiry forecasts from {origin}")
    record = horizons.load_record()
    first = rows.iloc[0]
    return {"symbol": symbol, "origin_date": str(first["origin_date"]), "spot": float(first["spot"]),
            "vix_close": first["vix_close"], "method": "garch",
            "validated_on": record and {"dev_years": record["dev_years"], "gate_coverage_80": record["gate_coverage_80"],
                                        "frozen_at": record["frozen_at"]},
            "expiries": [_expiry_row(r, record) for _, r in rows.iterrows()]}


@router.get("/monitoring", summary="Is the forecast still calibrated?")
def monitor(symbol: str = Query("SPX")):
    """Per method, over the last 26 and 52 weeks with a known outcome: 80% / 90% band coverage, width, pinball,
    coverage by VIX regime, and a drift flag (exact binomial test of the 80% coverage, p < 0.05)."""
    _check(symbol)
    with _connection() as conn:
        forecasts = store.read_forecasts(conn, symbol)
    if forecasts.empty:
        raise HTTPException(status_code=404, detail="No forecasts yet: POST /v1/predict/refresh")
    result = monitoring.monitor(forecasts)
    with _connection() as conn:
        result["horizons"] = monitoring.monitor_horizons(store.read_expiry_forecasts(conn, symbol))
    result["scheduler"] = ({"running": True, "last_run": SCHEDULER.last_run, "last_daily": SCHEDULER.last_daily,
                            "last_error": SCHEDULER.last_error}
                           if SCHEDULER else {"running": False})
    return result


@router.post("/refresh", summary="Forecast any new week now")
def refresh(symbol: str = Query("SPX")):
    """Rebuild the dataset and store a forecast for every complete week that doesn't have one, and expiry forecasts
    for every session close without them. Safe to repeat."""
    _check(symbol)
    with _connection() as conn:
        return {**serving.refresh(conn), "expiries": serving.refresh_expiries(conn)}
