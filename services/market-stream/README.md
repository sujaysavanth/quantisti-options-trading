# Market Stream Service

Low-latency quote distribution layer that sits between raw data collectors (Yahoo index polling, broker feeds, mock publishers) and every component that needs “live” prices (paper-trading simulator, strategy dashboard).

## Features

- **Quote Upserts** – REST endpoint (`POST /v1/quotes`) to push the latest underlying/option quotes from any collector.
- **Quote Snapshots** – REST endpoint (`GET /v1/quotes` and `/v1/quotes/{symbol}`) to fetch the latest values for reconciliation.
- **WebSocket Broadcasts** – `/ws/quotes` streams updates to connected clients (UI, simulator) as soon as a new tick arrives.
- **In-Memory Store** – Keeps only the most recent quote per instrument, avoiding bulky historical storage when only live P&L is required.

## Running Locally

```bash
cd services/market-stream
pip install -e .
PORT=8090 uvicorn app.main:app --reload
```

### Docker

```bash
docker build -t quantisti-market-stream services/market-stream
docker run -p 8090:8090 quantisti-market-stream
```

## Pushing Quotes

Use the included helper script to push mock ticks:

```bash
python scripts/mock_quote_publisher.py --symbol SPX --price 7650 --legs SPXW:7600:PUT SPXW:7700:CALL
```

or POST manually:

```bash
curl -X POST http://localhost:8090/v1/quotes \
  -H "Content-Type: application/json" \
  -d '{
        "symbol": "SPX",
        "last_price": 19812.35,
        "timestamp": "2025-11-18T10:32:00Z",
        "legs": [
          {"identifier": "SPXW261002P07600000", "strike": 7600, "option_type": "PUT", "expiry": "2026-10-02", "bid": 142.5, "ask": 145.0, "last": 143.1}
        ]
      }'
```

Clients can subscribe to ws://localhost:8090/ws/quotes to receive:

```json
{
  "type": "quote",
  "data": {
    "symbol": "SPX",
    "last_price": 19812.35,
    "timestamp": "2025-11-18T10:32:00+00:00",
    "legs": [...]
  }
}
```

## Next Steps

- Wire in a real-time options feed (broker websocket or a paid OPRA provider) behind the same `POST /v1/quotes` contract.
- Persist optional short rolling window per instrument if the dashboard needs tiny charts.
- Authenticate REST/WebSocket calls once integrated behind the gateway.

### Yahoo Finance Collector (S&P 500 index)

```bash
python scripts/yahoo_collector.py \
  --symbol ^GSPC \
  --push-symbol SPX \
  --market-stream-url http://localhost:8090
```

Adjust `--interval`/`--range` to taste. Yahoo's feed is undocumented and throttled, so keep polls to ~60s.

### Option leg quotes

There is no free real-time SPX option feed. Use `scripts/mock_quote_publisher.py` (above) to push legs for
local development; end-of-day listed chains are collected separately by `scripts/spx_chain_snapshot.py`
into Postgres for the market service.
