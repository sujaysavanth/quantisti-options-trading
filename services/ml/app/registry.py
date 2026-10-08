"""The model registry: the frozen forecaster, saved so the prediction endpoint (ML-4) can load it.

A registered version bundles the fitted forecaster, its per-regime conformal adjustments (if the choice
uses calibration) and the description from model_choice.json. Loaded through MLflow's pyfunc interface,
`predict` takes feature rows (as in weekly_features: the model's features plus vix_close and
sessions_next) and returns the quantiles q05..q95 of next week's close return.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Dict, Optional

import joblib
import mlflow.pyfunc
import numpy as np
import pandas as pd

from .evaluation.walkforward import QCOLS
from .forecasting.conformal import apply_adjustments
from .tracking import REGISTERED_MODEL


class WeeklyRangeModel(mlflow.pyfunc.PythonModel):
    def load_context(self, context):
        self.bundle = joblib.load(context.artifacts["bundle"])

    def predict(self, context, model_input: pd.DataFrame, params=None) -> pd.DataFrame:
        b = self.bundle
        q = b["forecaster"].predict(model_input, None)
        if b.get("adjustments"):
            q = apply_adjustments(q, model_input["vix_close"].to_numpy(dtype=float), b["adjustments"])
        return pd.DataFrame(np.asarray(q, dtype=float), columns=QCOLS, index=model_input.index)


def register(mlflow_module, forecaster, choice: Dict, adjustments: Optional[Dict], example: pd.DataFrame) -> str:
    """Log the bundle in the active run and register it; returns the new version number."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bundle.joblib"
        joblib.dump({"forecaster": forecaster, "adjustments": adjustments, "choice": choice}, path)
        info = mlflow_module.pyfunc.log_model(
            name="forecaster", python_model=WeeklyRangeModel(), artifacts={"bundle": str(path)},
            input_example=example, registered_model_name=REGISTERED_MODEL)
    return str(info.registered_model_version)


def load(version: str = "latest"):
    """The registered forecaster as a pyfunc model (ML-4 uses this)."""
    from .tracking import _setup
    _setup()
    return mlflow.pyfunc.load_model(f"models:/{REGISTERED_MODEL}/{version}")
