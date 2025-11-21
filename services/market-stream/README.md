# Market Stream Service

Low-latency quote distribution layer that sits between raw data collectors (broker/NSE feeds, Alpha Vantage 1‑minute polling, etc.) and every component that needs “live” prices (paper-trading simulator, strategy dashboard).

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
python scripts/mock_quote_publisher.py --symbol NIFTY --price 19800
```

or POST manually:

```bash
curl -X POST http://localhost:8090/v1/quotes \
  -H "Content-Type: application/json" \
  -d '{
        "symbol": "NIFTY",
        "last_price": 19812.35,
        "timestamp": "2025-11-18T10:32:00Z",
        "legs": [
          {"identifier": "NIFTY25NOV19500PE", "strike": 19500, "option_type": "PUT", "expiry": "2025-11-25", "bid": 142.5, "ask": 145.0, "last": 143.1}
        ]
      }'
```

Clients can subscribe to ws://localhost:8090/ws/quotes to receive:

```json
{
  "type": "quote",
  "data": {
    "symbol": "NIFTY",
    "last_price": 19812.35,
    "timestamp": "2025-11-18T10:32:00+00:00",
    "legs": [...]
  }
}
```

## Next Steps

- Wire in actual collectors (Alpha Vantage minute polling, broker websocket adapter).
- Persist optional short rolling window per instrument if the dashboard needs tiny charts.
- Authenticate REST/WebSocket calls once integrated behind the gateway.

### Alpha Vantage Collector (US symbols)

Set your API key in `.env.development` (`ALPHAVANTAGE_API_KEY=...`) and run:

```bash
python scripts/alpha_vantage_collector.py \
  --symbol SPY \
  --market-stream-url http://localhost:8090
```

Add `--oneshot` for a single fetch or let it run continuously (default 60s). Alpha Vantage intraday does not cover NIFTY; use Yahoo or broker feeds for Indian symbols.

### Yahoo Finance Collector (NIFTY-friendly)

```bash
python scripts/yahoo_collector.py \
  --symbol ^NSEI \
  --market-stream-url http://localhost:8090
```

Adjust `--interval`/`--range` to taste. Yahoo’s feed is undocumented and throttled, so keep polls to ~60s.

### NSE Option Chain Collector (leg quotes)

```bash
python scripts/nse_option_chain_collector.py \
  --symbol NIFTY \
  --market-stream-url http://localhost:8090 \
  --max-legs 200
```

This polls the public NSE option-chain JSON (updates every few minutes) and pushes the underlying price plus the most recent option leg quotes (bid/ask/last, IV). Increase `--max-legs` to include more strikes, but be mindful of payload sizes.
