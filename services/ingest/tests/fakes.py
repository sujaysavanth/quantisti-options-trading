"""An in-memory stand-in for confluent_kafka.Producer."""

from __future__ import annotations

import json


class FakeMsg:
    def __init__(self, topic, key, value):
        self._topic, self.key, self.value = topic, key, value

    def topic(self):
        return self._topic


class FakeProducer:
    def __init__(self, fail_topics=()):
        self.sent = []          # (topic, key str, decoded JSON)
        self._pending = []
        self.fail_topics = set(fail_topics)

    def produce(self, topic, key, value, on_delivery):
        self.sent.append((topic, key.decode(), json.loads(value)))
        self._pending.append((FakeMsg(topic, key, value), on_delivery))

    def poll(self, timeout):
        pending, self._pending = self._pending, []
        for msg, cb in pending:
            cb("broker down" if msg.topic() in self.fail_topics else None, msg)
        return len(pending)

    def flush(self, timeout):
        self.poll(0)
        return 0

    def list_topics(self, timeout):
        return {}
