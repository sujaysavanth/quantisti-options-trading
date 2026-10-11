# Strategy engine: original design

**Status: not built.** This is the multi-signal scoring planned for the first (NIFTY) version: market signals scored
by category, aggregated, and turned into strategies with a win probability and risk/reward. What exists instead is
the forecast-based recommendation in the dashboard (`services/strategy-dashboard/data/recommend.ts`): each defined-
risk strategy is scored by its expected P&L under the ml service's range forecast, after half the bid/ask, over its max
loss. The call/put open-interest ratio and VIX-based volatility features exist (market service, ml features); the IV
percentile score, candlestick and trend signals, and sentiment (the RBI news feed would now be Fed/news sentiment)
do not.

```mermaid
flowchart LR
    Start((Start)) --> OptionChain[Option Chain Data]
    Start --> Candlestick[Candlestick Patterns]
    Start --> RBI[RBI News Feed]
    Start --> Ticker[Ticker Symbol]
    Start --> IV[IV Data]
    Start --> Greeks[Option Greeks]

    OptionChain --> Analysis[Analysis Layer]
    Candlestick --> Analysis
    RBI --> Analysis
    Ticker --> Analysis
    IV --> Analysis
    Greeks --> Analysis

    Analysis --> VA[Volatility Analysis]
    Analysis --> TA[Technical Pattern Analysis]
    Analysis --> SA[Sentiment Analysis]

    VA --> IVP[IV Percentile Score]
    VA --> ZScore[Z-Score vs 1-year Mean]

    TA --> Candle[Candlestick Signal]
    TA --> Trend[Trend Strength Score]

    SA --> Sentiment[RBI Sentiment Score]
    SA --> OI[Call/Put OI Ratio]

    IVP --> ScoreAgg[Score Aggregation Layer]
    ZScore --> ScoreAgg
    Candle --> ScoreAgg
    Trend --> ScoreAgg
    Sentiment --> ScoreAgg
    OI --> ScoreAgg

    ScoreAgg --> StratGen[Strategy Generator]
    StratGen --> Select[Option Strategies Selection]
    StratGen --> WinProb[Win Probability Assignment]
    StratGen --> RR[Risk-to-Reward Ratio Calculation]

    Select --> JSON[JSON Response Generator]
    WinProb --> JSON
    RR --> JSON

    JSON --> Table[Strategy Table]
    JSON --> Graphs[Graphable Data]
    JSON --> Breakdown[Analysis Breakdown by Category]

    Table --> UI[UI Output]
    Graphs --> UI
    Breakdown --> UI
    UI --> End((End))
```
