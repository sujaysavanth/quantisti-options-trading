"""Reads Kafka, keeps BridgeState up to date, and POSTs the quote to market-stream.

Where to start reading (offsets):
- "earliest" would replay up to 7 days of chains on every start: slow, and
  all but the last message per expiry gets thrown away.
- "latest" would start empty and stay empty until the next poll, which after
  hours means tomorrow morning.
So on startup the bridge seeks each partition back a few messages from its
end (SEEK_BACK). That is enough to rebuild the latest SPX price, chain per
expiry and rate. "Newest wins" in BridgeState, so the replay order across
partitions doesn't matter.

The bridge never commits offsets. It doesn't need to: it always rebuilds from
the end, and nothing breaks if a message is seen twice.

Posting: at most once every POST_EVERY when something changed, and at least
once every RESEND_EVERY regardless, so a restarted market-stream (which keeps
quotes in memory only) is refilled within a minute.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Optional, Tuple

import httpx

from ..producers.envelope import Envelope
from ..producers.kafka import TOPIC_BARS, TOPIC_CHAIN, TOPIC_DAILY
from .state import BridgeState

log = logging.getLogger(__name__)

# Messages to re-read per partition on startup.
SEEK_BACK: Dict[str, int] = {TOPIC_CHAIN: 60, TOPIC_BARS: 5, TOPIC_DAILY: 30}
POST_EVERY = timedelta(seconds=5)
RESEND_EVERY = timedelta(seconds=60)


def start_offset(low: int, high: int, back: int) -> int:
    """Offset `back` messages before the end of a partition, but not before its oldest retained message."""
    return max(low, high - back)


def should_post(now: datetime, last_post: Optional[datetime], changed: bool) -> bool:
    if last_post is None:
        return changed
    if changed and now - last_post >= POST_EVERY:
        return True
    return now - last_post >= RESEND_EVERY


class Bridge:
    def __init__(self, bootstrap: str, market_stream_url: str, state: BridgeState,
                 post: Optional[Callable[[dict], None]] = None):
        self.bootstrap = bootstrap
        self.state = state
        url = market_stream_url.rstrip("/") + "/v1/quotes"
        self._post = post or (lambda quote: httpx.post(url, json=quote, timeout=10).raise_for_status())
        self.changed = False
        self.last_post: Optional[datetime] = None
        # End offset of each partition at startup that the replay hasn't reached yet. Posting waits
        # until it's empty, so a half-replayed state (some expiries missing) is never published.
        self.catching_up: Dict[Tuple[str, int], int] = {}

    def track_replay(self, topic: str, partition: int, offset: int) -> None:
        key = (topic, partition)
        if key in self.catching_up and offset + 1 >= self.catching_up[key]:
            del self.catching_up[key]
            if not self.catching_up:
                log.info("replay done")

    def handle(self, raw: bytes) -> None:
        try:
            self.changed |= self.state.apply(Envelope.from_bytes(raw))
        except ValueError as exc:            # pydantic's ValidationError and bad JSON are both ValueErrors
            log.warning("skipping bad message: %s", exc)

    def maybe_post(self, now: datetime) -> bool:
        if self.catching_up or not should_post(now, self.last_post, self.changed):
            return False
        quote = self.state.to_quote(now)
        if quote is None:
            return False
        self.last_post = now
        try:
            self._post(quote)
            self.changed = False
            log.info("posted SPX %.2f, %d legs over %d expiries (default %s), quoted %s",
                     quote["last_price"], len(quote["legs"]), len(quote["expiries"]), quote["default_expiry"],
                     quote["quoted_at"])
            return True
        except Exception as exc:             # market-stream down: keep `changed`, retry after POST_EVERY
            log.warning("posting to market-stream failed: %s", exc)
            return False

    def _assign(self, consumer) -> None:
        from confluent_kafka import TopicPartition
        topics = consumer.list_topics(timeout=10).topics
        assignment = []
        for topic, back in SEEK_BACK.items():
            for partition in topics[topic].partitions:
                low, high = consumer.get_watermark_offsets(TopicPartition(topic, partition), timeout=10)
                assignment.append(TopicPartition(topic, partition, start_offset(low, high, back)))
                if high > low:
                    self.catching_up[(topic, partition)] = high
        consumer.assign(assignment)
        log.info("reading %d partitions from %d messages before the end", len(assignment), sum(SEEK_BACK.values()))

    def run(self, stop: threading.Event) -> None:
        from confluent_kafka import Consumer
        consumer = Consumer({
            "bootstrap.servers": self.bootstrap,
            "group.id": "stream-bridge",      # shows up in Kafka UI; offsets are never committed
            "enable.auto.commit": False,
        })
        try:
            self._assign(consumer)
            while not stop.is_set():
                msg = consumer.poll(1.0)
                if msg is not None:
                    if msg.error():
                        log.warning("kafka: %s", msg.error())
                    else:
                        self.handle(msg.value())
                        self.track_replay(msg.topic(), msg.partition(), msg.offset())
                self.maybe_post(datetime.now(timezone.utc))
        finally:
            consumer.close()
