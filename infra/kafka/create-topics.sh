#!/usr/bin/env bash
# Create the Quantisti topics and enforce their retention. Safe to re-run.
#
#   name                      partitions  retention  key
#   market.bars.1m            3           7 days     symbol
#   market.daily              1           7 days     dataset:symbol
#   options.chain.quotes      3           7 days     symbol:expiry (one message per expiry per poll)
#   ingest.backfill.requests  1           7 days     dataset:date
#   ingest.dlq                1           30 days    (bad messages from any consumer)
#
# Postgres is the system of record; Kafka only needs to hold data long enough
# for consumers to catch up or replay, hence the short retention.
set -euo pipefail

BOOTSTRAP="${BOOTSTRAP:-kafka:9092}"
BIN=/opt/kafka/bin
DAY_MS=86400000

topic() {
  local name=$1 partitions=$2 retention_days=$3
  "$BIN/kafka-topics.sh" --bootstrap-server "$BOOTSTRAP" --create --if-not-exists \
    --topic "$name" --partitions "$partitions" --replication-factor 1
  # --create --if-not-exists leaves an existing topic untouched, so set retention separately.
  "$BIN/kafka-configs.sh" --bootstrap-server "$BOOTSTRAP" --alter --entity-type topics --entity-name "$name" \
    --add-config "retention.ms=$((retention_days * DAY_MS)),cleanup.policy=delete" > /dev/null
  echo "ready: $name (partitions=$partitions, retention=${retention_days}d)"
}

topic market.bars.1m 3 7
topic market.daily 1 7
topic options.chain.quotes 3 7
topic ingest.backfill.requests 1 7
topic ingest.dlq 1 30

echo "--- topics on $BOOTSTRAP"
"$BIN/kafka-topics.sh" --bootstrap-server "$BOOTSTRAP" --list
