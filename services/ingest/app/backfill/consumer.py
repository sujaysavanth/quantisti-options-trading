"""Reads ingest.backfill.requests and hands each request to the Worker.

A work queue, so unlike the stream bridge this consumer commits offsets: consumer group
"ingest-backfill" remembers how far it got, and a restart carries on from there instead of
redoing every request. It commits after handling a message, so a crash mid-request means
that request runs again (at-least-once), which is harmless: data upserts are idempotent.

Before working, it checks the gap is still `requested` and the request is the latest attempt,
so stale or replayed requests are skipped. Malformed requests go to ingest.dlq.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Callable, Optional

from ..db import connect
from ..gaps import store
from ..producers.dlq import dead_letter
from ..producers.envelope import BackfillPayload, Envelope
from ..producers.kafka import TOPIC_BACKFILL, Publisher
from .worker import Outcome, Worker

log = logging.getLogger(__name__)

GROUP_ID = "ingest-backfill"


def current_gap(conn, req: BackfillPayload) -> Optional[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT status, attempts, split_part(detail, ' | ', 1) FROM ingest_gaps"
                    " WHERE dataset = %s AND symbol = %s AND gap_date = %s", (req.dataset, req.symbol, req.date))
        row = cur.fetchone()
    return dict(zip(("status", "attempts", "detail"), row)) if row else None


class BackfillConsumer:
    def __init__(self, bootstrap: str, database_url: str, publisher: Publisher, worker: Worker):
        self.bootstrap, self.database_url = bootstrap, database_url
        self.publisher, self.worker = publisher, worker
        self.handled = {"published": 0, "unrecoverable": 0, "failed": 0, "skipped": 0, "dlq": 0}
        self.last: Optional[dict] = None    # shown at GET /v1/gaps

    def handle(self, raw: bytes, connect_db: Callable = None) -> str:
        """One message -> what happened to it."""
        connect_db = connect_db or (lambda: connect(self.database_url))
        try:
            env = Envelope.from_bytes(raw)
            if not isinstance(env.payload, BackfillPayload):
                raise ValueError(f"expected backfill.v1, got {env.schema_name}")
        except ValueError as exc:           # bad JSON and pydantic's ValidationError are both ValueErrors
            dead_letter(self.publisher, "backfill_worker", TOPIC_BACKFILL, f"bad request: {exc}", raw)
            self.publisher.flush(10)
            self.handled["dlq"] += 1
            return "dlq"

        req = env.payload
        with connect_db() as conn:
            gap = current_gap(conn, req)
            if gap is None or gap["status"] != "requested" or req.attempt < gap["attempts"]:
                self.handled["skipped"] += 1
                return "skipped"

            out: Outcome = self.worker.handle(req)
            self.publisher.flush(30)
            note = f"{gap['detail']} | attempt {req.attempt}: " + (f"sent {out.sent}" if out.kind == "published" else out.detail)
            store.set_status(conn, req.dataset, req.symbol, req.date,
                             "unrecoverable" if out.kind == "unrecoverable" else "requested", note)

        log.info("backfill %s %s %s attempt %d: %s %s", req.dataset, req.symbol, req.date, req.attempt,
                 out.kind, out.detail or out.sent)
        self.handled[out.kind] += 1
        self.last = {"at": datetime.now(timezone.utc), "dataset": req.dataset, "symbol": req.symbol,
                     "date": req.date, "outcome": out.kind, "detail": out.detail, "sent": out.sent}
        return out.kind

    def run(self, stop: threading.Event) -> None:
        from confluent_kafka import Consumer
        consumer = Consumer({
            "bootstrap.servers": self.bootstrap,
            "group.id": GROUP_ID,
            "auto.offset.reset": "earliest",   # first start: pick up requests made before the worker existed
            "enable.auto.commit": False,
        })
        consumer.subscribe([TOPIC_BACKFILL])
        log.info("backfill worker started")
        try:
            while not stop.is_set():
                msg = consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    log.warning("kafka: %s", msg.error())
                    continue
                try:
                    self.handle(msg.value())
                except Exception:
                    # e.g. Postgres down: leave the gap as is; the next scan requests it again.
                    log.exception("backfill request failed")
                consumer.commit(message=msg, asynchronous=False)
        finally:
            consumer.close()
            log.info("backfill worker stopped")
