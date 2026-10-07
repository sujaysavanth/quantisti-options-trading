"""Development years, holdout years, and the lock that keeps the holdout honest.

Every choice (model type, settings, feature groups, calibration) is made by looking at the development
years only. The holdout years are scored once, with the choice frozen in `model_choice.json` (committed to
the repo, so the record is public). Looking at the holdout, changing something, and looking again would
make it one more development set; `holdout_allowed` refuses a second run unless it is explicitly forced,
and a forced re-run is written into the file next to the first result.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

FIRST_TEST_YEAR = 2014
DEV_YEARS = range(FIRST_TEST_YEAR, 2021)           # 2014-2020, includes the 2018 and 2020 shocks
HOLDOUT_FIRST_YEAR = 2021                          # 2021 to the latest complete year in the data

CHOICE_FILE = Path(__file__).resolve().parents[2] / "model_choice.json"   # services/ml/model_choice.json


def holdout_years(last_year: int) -> range:
    return range(HOLDOUT_FIRST_YEAR, last_year + 1)


def load_choice(path: Path = CHOICE_FILE) -> Optional[Dict]:
    return json.loads(path.read_text(encoding="utf8")) if path.exists() else None


def freeze(choice: Dict, path: Path = CHOICE_FILE) -> Dict:
    """Record the development-period decision before the holdout is touched."""
    existing = load_choice(path)
    if existing and existing.get("holdout"):
        raise RuntimeError(f"{path} already has a holdout result; a new choice now would be chosen with hindsight")
    record = {**choice, "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "holdout": None}
    path.write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf8")
    return record


def holdout_allowed(path: Path = CHOICE_FILE, force: bool = False) -> Dict:
    choice = load_choice(path)
    if choice is None:
        raise RuntimeError("no frozen choice: run `python -m app.cli freeze ...` after the development evaluation")
    if choice.get("holdout") and not force:
        raise RuntimeError("the holdout has already been scored; re-running it turns it into a development set "
                           "(use --force to re-run anyway; the re-run is recorded)")
    return choice


def record_holdout(result: Dict, path: Path = CHOICE_FILE) -> Dict:
    choice = load_choice(path) or {}
    entry = {**result, "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if choice.get("holdout"):
        choice.setdefault("holdout_reruns", []).append(entry)       # never silently overwrite the first look
    else:
        choice["holdout"] = entry
    path.write_text(json.dumps(choice, indent=2, default=str) + "\n", encoding="utf8")
    return choice
