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
