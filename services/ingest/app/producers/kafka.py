"""Thin wrapper around confluent-kafka's Producer.

Keys decide partitions: Kafka hashes the key, so every message with the same
key (e.g. "SPX") lands in the same partition and stays in order. Different keys
may be read in parallel.

`send()` only queues the message; a background thread delivers it and calls
`_on_delivery` with the result. `flush()` waits for everything queued.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Optional

from .envelope import Envelope

log = logging.getLogger(__name__)

TOPIC_BARS = "market.bars.1m"
TOPIC_CHAIN = "options.chain.quotes"
TOPIC_DAILY = "market.daily"

PRODUCER_CONFIG = {
    # Idempotent producer: the broker drops duplicates caused by retries, and order per
    # partition is kept. Requires acks=all (wait for every in-sync replica).
    "enable.idempotence": True,
    "acks": "all",
    "linger.ms": 50,                 # wait briefly so a poll's messages go out in one batch
    "compression.type": "lz4",
    "message.timeout.ms": 60_000,    # give up (and report failure) after a minute
}


class Publisher:
    def __init__(self, bootstrap: str, producer: Any = None):
        if producer is None:
            from confluent_kafka import Producer
            producer = Producer({"bootstrap.servers": bootstrap, "client.id": "ingest", **PRODUCER_CONFIG})
        self._producer = producer        # injectable so tests can pass a fake
        self.delivered: Counter = Counter()
        self.failed: Counter = Counter()

    def _on_delivery(self, err, msg) -> None:
        if err is not None:
            self.failed[msg.topic()] += 1
            log.error("delivery to %s failed: %s", msg.topic(), err)
        else:
            self.delivered[msg.topic()] += 1

    def send(self, topic: str, key: str, envelope: Envelope) -> None:
        kwargs = dict(key=key.encode(), value=envelope.to_bytes(), on_delivery=self._on_delivery)
        try:
            self._producer.produce(topic, **kwargs)
        except BufferError:
            # Local queue full: let it drain, then try once more.
            self._producer.poll(1)
            self._producer.produce(topic, **kwargs)
        self._producer.poll(0)           # serve delivery callbacks of earlier messages

    def flush(self, timeout: float = 30) -> int:
        """Wait for queued messages; returns how many are still undelivered."""
        return self._producer.flush(timeout)

    def ping(self, timeout: float = 5) -> Optional[str]:
        """None if the broker answers, else the error text."""
        try:
            self._producer.list_topics(timeout=timeout)
            return None
        except Exception as exc:  # KafkaException on timeout
            return str(exc)
