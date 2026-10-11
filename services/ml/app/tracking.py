"""Experiment tracking with MLflow: every evaluation, ablation, freeze and holdout run is recorded.

Each run stores what produced its numbers: the command, models and feature groups, test years, the git
commit (and whether the working tree had uncommitted changes), the feature version and a fingerprint of
the data, plus every score and the report files. The frozen model goes into the model registry, which the
prediction endpoint (ML-4) loads from.

Storage is local and git-ignored: run records and the registry in data/ml/mlflow.db (SQLite, MLflow's
recommended backend; its file store is in maintenance mode), files in data/ml/mlruns.
Browse them with:  mlflow ui --backend-store-uri sqlite:///data/ml/mlflow.db --port 5050
Set MLFLOW_TRACKING_URI to use a tracking server instead. ML_TRACKING=off turns tracking off.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

EXPERIMENT = "spx-weekly-range"
REGISTERED_MODEL = "spx-weekly-range"
def repo_root() -> Optional[Path]:
    """The checkout this file lives in (the folder with services/), or None inside the service container."""
    return next((p for p in Path(__file__).resolve().parents if (p / "services").is_dir()), None)


REPO = repo_root()


def data_dir() -> Path:
    """data/ml at the repo root on your machine; /app/data/ml (mounted) in the container."""
    return (REPO or Path.cwd()) / "data" / "ml"


def enabled() -> bool:
    return os.getenv("ML_TRACKING", "on").lower() not in ("off", "0", "false")


def _setup():
    import mlflow
    data_dir().mkdir(parents=True, exist_ok=True)
    uri = os.getenv("MLFLOW_TRACKING_URI") or f"sqlite:///{(data_dir() / 'mlflow.db').resolve().as_posix()}"
    mlflow.set_tracking_uri(uri)
    if mlflow.get_experiment_by_name(EXPERIMENT) is None:
        mlflow.create_experiment(EXPERIMENT, artifact_location=(data_dir() / "mlruns").resolve().as_uri())
    mlflow.set_experiment(EXPERIMENT)
    return mlflow


def git_state() -> Dict[str, str]:
    """From the checkout; in the container (no git) from GIT_COMMIT, set at deploy time."""
    if REPO is None:
        return {"git_commit": os.getenv("GIT_COMMIT", "unknown")[:12], "git_dirty": "unknown"}

    def git(*args):
        try:
            return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            return ""
    return {"git_commit": git("rev-parse", "HEAD")[:12] or "unknown",
            "git_dirty": "yes" if git("status", "--porcelain", "--untracked-files=no") else "no"}


def data_fingerprint(data: pd.DataFrame) -> str:
    """Changes whenever the weeks or their outcomes change (new week, refilled gap, re-imported chains)."""
    key = data[["anchor_date", "close_ret"]].to_csv(index=False).encode()
    return hashlib.sha256(key).hexdigest()[:12]


def metric_name(*parts: str) -> str:
    """MLflow metric names allow letters, digits and _-./ and spaces; '+conformal' becomes '_conformal'."""
    return re.sub(r"[^A-Za-z0-9_\-./ ]", "_", ".".join(parts))


@contextmanager
def run(name: str, params: Dict, data: Optional[pd.DataFrame] = None):
    """A tracked run (or nothing, if tracking is off). Yields the mlflow module or None."""
    if not enabled():
        with nullcontext():
            yield None
        return
    mlflow = _setup()
    from .dataset.features import FEATURE_VERSION
    tags = {**git_state(), "feature_version": str(FEATURE_VERSION), "command": name}
    if data is not None:
        tags.update({"data_fingerprint": data_fingerprint(data), "weeks": str(len(data))})
    with mlflow.start_run(run_name=name, tags=tags):
        mlflow.log_params({k: (",".join(map(str, v)) if isinstance(v, (list, tuple, range)) else v)
                           for k, v in params.items()})
        yield mlflow


def log_summary(mlflow, summary: Dict, prefix: str = "") -> None:
    """Every forecaster's scores, coverage per regime and significance, as metrics."""
    if mlflow is None:
        return
    metrics = {}
    for name, s in summary.get("overall", {}).items():
        for k in ("pinball", "coverage_80", "coverage_90", "width_80", "winkler_80"):
            if s.get(k) is not None:
                metrics[metric_name(prefix + name, k)] = float(s[k])
    for regime, scores in summary.get("by_regime", {}).items():
        short = regime.split(" ")[0]
        for name, s in scores.items():
            if s.get("coverage_80") is not None:
                metrics[metric_name(prefix + name, "coverage_80", short)] = float(s["coverage_80"])
    for name, by_ref in summary.get("significance", {}).items():
        for ref, t in by_ref.items():
            if t.get("n"):
                metrics[metric_name(prefix + name, "vs", ref, "p_value")] = float(t["p_value"])
                metrics[metric_name(prefix + name, "vs", ref, "relative")] = float(t["relative"])
    mlflow.log_metrics(metrics)


def log_files(mlflow, paths: Iterable[Path]) -> None:
    if mlflow is not None:
        for p in paths:
            mlflow.log_artifact(str(p))
