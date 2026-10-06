"""market_spec.py is copied into market, simulator, ingest and stream-processing. Fail if the copies drift."""

from pathlib import Path

import pytest

SERVICES = Path(__file__).resolve().parents[2]
COPIES = [SERVICES / name / "app" / "market_spec.py" for name in ("market", "simulator", "ingest")] + [
    SERVICES / "stream-processing" / "jobs" / "market_spec.py"]


def code(path: Path) -> str:
    """Everything after the module docstring (each copy's docstring explains where it lives)."""
    text = path.read_text(encoding="utf8")
    return text[text.index("from __future__ import annotations"):]


@pytest.mark.skipif(not all(p.exists() for p in COPIES), reason="needs the full repo checkout, not a single-service image")
def test_market_spec_copies_are_identical():
    reference = code(COPIES[0])
    for path in COPIES[1:]:
        assert code(path) == reference, f"{path} differs from {COPIES[0]}; copy the change across"
