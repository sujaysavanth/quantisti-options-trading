from datetime import datetime, timezone

from app.producers.envelope import BarPayload, wrap
from app.producers.kafka import PRODUCER_CONFIG, TOPIC_BARS, Publisher
from tests.fakes import FakeProducer

TS = datetime(2026, 10, 5, 14, 30, tzinfo=timezone.utc)
ENV = wrap("bars.v1", "yahoo", 15, BarPayload(symbol="SPX", interval="1m", ts=TS, open=1, high=1, low=1, close=1, volume=0))


def test_send_uses_topic_key_and_json_value():
    fake = FakeProducer()
    pub = Publisher("unused", producer=fake)
    pub.send(TOPIC_BARS, "SPX", ENV)
    assert pub.flush() == 0
    topic, key, value = fake.sent[0]
    assert (topic, key, value["schema"], value["payload"]["symbol"]) == ("market.bars.1m", "SPX", "bars.v1", "SPX")
    assert pub.delivered[TOPIC_BARS] == 1 and not pub.failed


def test_failed_deliveries_are_counted():
    pub = Publisher("unused", producer=FakeProducer(fail_topics={TOPIC_BARS}))
    pub.send(TOPIC_BARS, "SPX", ENV)
    pub.flush()
    assert pub.failed[TOPIC_BARS] == 1


def test_idempotent_settings():
    assert PRODUCER_CONFIG["enable.idempotence"] is True and PRODUCER_CONFIG["acks"] == "all"
