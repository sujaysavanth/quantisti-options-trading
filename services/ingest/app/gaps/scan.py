"""One gap scan, start to finish, plus the cheap re-check that runs in between.

    recheck   open gaps whose data has arrived -> filled
    scan      recheck, find_gaps, record them, then per `requested` gap:
                fewer than MAX_ATTEMPTS requests so far -> publish one more backfill request
                MAX_ATTEMPTS reached and still missing   -> unrecoverable + the request goes to ingest.dlq

A gap is only marked filled when its data is in the table. Publishing a request proves nothing:
the worker might fail, or Spark might reject what it sends.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional

from ..producers.dlq import dead_letter
from ..producers.envelope import BackfillPayload, wrap
from ..producers.kafka import TOPIC_BACKFILL, Publisher
from . import store
from .detector import find_gaps

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


@dataclass
class ScanResult:
    at: datetime
    found: int = 0                      # gaps the detector sees right now
    filled: int = 0                     # open gaps whose data has arrived since the last check
    requested: int = 0                  # backfill requests published
    gave_up: int = 0                    # moved to unrecoverable after MAX_ATTEMPTS
    by_dataset: Dict[str, int] = field(default_factory=dict)


def decide(status: str, attempts: int) -> Optional[str]:
    """What to do with a gap the detector still sees: 'request', 'give_up', or None (leave it)."""
    if status != "requested":
        return None
    return "request" if attempts < MAX_ATTEMPTS else "give_up"


def request_message(dataset: str, symbol: str, day, attempt: int, now: datetime):
    payload = BackfillPayload(dataset=dataset, symbol=symbol, date=day, attempt=attempt)
    return f"{dataset}:{day}", wrap("backfill.v1", "gap_detector", 0, payload, now)


def recheck(conn) -> int:
    filled = 0
    for g in store.open_gaps(conn):
        if store.is_present(conn, g["dataset"], g["symbol"], g["gap_date"]):
            store.set_status(conn, g["dataset"], g["symbol"], g["gap_date"], "filled")
            filled += 1
    if filled:
        log.info("gap recheck: %d filled", filled)
    return filled


def scan(conn, publisher: Publisher, now: Optional[datetime] = None) -> ScanResult:
    now = now or datetime.now(timezone.utc)
    result = ScanResult(at=now, filled=recheck(conn))
    gaps = find_gaps(store.load_coverage(conn, now), now)
    result.found = len(gaps)
    for g in gaps:
        result.by_dataset[g.dataset] = result.by_dataset.get(g.dataset, 0) + 1

    for row in store.upsert_gaps(conn, gaps):
        action = decide(row["status"], row["attempts"])
        key = (row["dataset"], row["symbol"], row["gap_date"])
        if action == "request":
            attempt = row["attempts"] + 1
            msg_key, envelope = request_message(*key, attempt, now)
            publisher.send(TOPIC_BACKFILL, msg_key, envelope)
            store.set_attempts(conn, *key, attempt)
            result.requested += 1
        elif action == "give_up":
            reason = f"still missing after {row['attempts']} backfill attempts"
            _, envelope = request_message(*key, row["attempts"], now)
            dead_letter(publisher, "gap_detector", TOPIC_BACKFILL, reason, envelope.to_bytes(), now)
            store.set_status(conn, *key, "unrecoverable", f"{row['detail']} | {reason}")
            result.gave_up += 1
    publisher.flush(30)
    log.info("gap scan: %d gaps %s, %d filled, %d requested, %d gave up",
             result.found, result.by_dataset, result.filled, result.requested, result.gave_up)
    return result
