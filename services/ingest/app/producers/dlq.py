"""Send a message the ingest service gave up on to ingest.dlq, in the same shape the Spark jobs use:

    key   = the topic it came from
    value = {"job": "backfill", "topic": "ingest.backfill.requests", "reason": "...",
             "failed_at": "...", "value": "<the original message, as a string>"}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional, Union

from .kafka import TOPIC_DLQ, Publisher


def dead_letter(publisher: Publisher, job: str, topic: str, reason: str, value: Union[str, bytes],
                now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    original = value.decode(errors="replace") if isinstance(value, bytes) else value
    body = {"job": job, "topic": topic, "reason": reason,
            "failed_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "value": original}
    publisher.send_raw(TOPIC_DLQ, topic, json.dumps(body).encode())
