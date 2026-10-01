# UI Reference Study

Design references for the simulator frontend, gathered 2026-09-29. Each section lists **who does it best**, **what to copy**, and **how it maps to this project**.

---

## 1. Options chain

### Best-in-class references

| Product | Why it's the reference |
|---|---|
| **tastytrade** | Widely rated the top options platform. Three chain modes (Table / Curve / Active); expirations listed with DTE + IVx; one-click spread building straight from the chain; POP, expected move, max P/L always visible. |
| **OptionStrat** | Best visual strategy builder. Click strikes to add legs, P/L heat-map over price × time, IV/date sliders, 50+ strategy templates. |
| **TradingView** | Cleanest data table: strike in center, calls left / puts right; calls-only / puts-only / straddle toggle; multi-expiration view; filters for expiry, strike range, bid-ask spread; column picker (24 fields per side). |
| **thinkorswim** | Density benchmark: collapsible expiration groups, configurable columns, analysis tab with risk graph. |
| **Robinhood** | Simplest beginner flow: one side at a time, big "breakeven" / "to profit" callouts. Reference for a "simple mode". |

### Layout to build

```
┌ AAPL 227.41 ▲ +1.23 (+0.54%)   IV Rank 34   Exp move ±6.10 ─────────────── [Table|Curve] ⚙ ┐
│ Expirations:  Oct 3 (4d)  Oct 10 (11d)  [Oct 17 (18d)]  Nov 21 (53d) ...   IVx per chip       │
├──────────────── CALLS ────────────────┬ STRIKE ┬──────────────── PUTS ───────────────────────┤
│  Δ    IV    OI     Vol   Bid    Ask   │        │  Bid    Ask   Vol    OI     IV    Δ          │
│ .72  28.1  4,210  1,022  9.80  9.95   │  220   │  2.41   2.47  2,318  6,004  29.4  -.28      │  ← ITM calls tinted
│ .61  27.6  ...                        │  225   │  ...                                        │
│ ─────────────────────── ▸ 227.41 spot line ──────────────────────────────────────────────── │
│ .49  27.2  ...                        │  230   │  ...                                        │  ← ITM puts tinted
└───────────────────────────────────────┴────────┴─────────────────────────────────────────────┘
  [ Leg builder: +1 C 230 / -1 C 235  ·  Debit 1.85  ·  Max P +3.15  ·  Max L -1.85  ·  POP 41% ]
```

Rules to adopt:

- **Strike column centered**, calls left, puts right; bid/ask mirrored so they sit next to the strike.
- **Spot price as a horizontal divider row** between strikes, auto-scrolled into view on load.
- **ITM tint** at ~8–12% opacity of a neutral/accent hue (not red/green — those mean direction only).
- **Expiration chips** with DTE and per-expiry IV; default to the nearest monthly.
- **Click bid → sell leg, click ask → buy leg** (tastytrade/OptionStrat convention). Legs accumulate in a sticky footer with net debit/credit, max P/L, breakevens, POP, net Greeks.
- **Column picker + presets** ("Basic": bid/ask/vol/OI; "Greeks": Δ Γ Θ ν; "Vol": IV, IV-skew).
- **Strike-range filter** (±N strikes or ±X% from spot) instead of rendering the whole chain.
- **Curve view**: P/L at expiry (solid) and at today/T+N (dashed), shaded profit/loss zones, breakeven markers, spot marker, sliders for date and IV shift.
- Volume/OI can be shown as a thin in-cell bar to spot liquidity without reading numbers.

Project note: `yfinance`'s `Ticker.option_chain(date)` gives bid/ask/last/volume/OI/IV but **no Greeks**, so the backend needs a Black-Scholes pricer (price + Greeks + POP) — a natural addition to `risk.py` or a new `options.py`.

---

## 2. Dashboard / simulator workspace

References: **TradingView** (fixed chart center, tool rails on edges), **Binance** (five live regions that stay readable), **Robinhood Legend** (beginner-to-pro desktop layout), **Bloomberg** (density), **QuantConnect** (backtest results page).

- **Tiled panels, not floating.** Chart and order/leg entry never collapse; watchlist and settings collapse first.
- **Dark-first**, near-black canvas (not `#000`), elevation by lightness steps, no drop shadows.
- **Two chromatic hues only**: green = up/profit/buy, red = down/loss/sell. Everything else is one neutral at graded opacities (100 / 75 / 45 / 25 / 10 / 5%).
- **Never color alone**: pair with ▲▼ icons, +/− signs, "Long/Short" text badges (colorblind users).
- **Monospace with tabular figures for every number** (JetBrains Mono / IBM Plex Mono), sans for prose (Inter). Right-align numerics so decimals line up.
- **Compact density**: 11–13px data text, 22–28px table rows, 4–8px panel padding.
- **Every panel has five states**: loading (skeleton), empty, error (inline retry), stale/disconnected (dimmed + "last update HH:MM:SS"), normal. Use "—" for missing values, never blank.
- **Price flash** on update (brief tint, then fade) rather than persistent color.
- Keyboard shortcuts for core actions with a `?` overlay.

### Backtest / risk results page (QuantConnect, Composer pattern)

- KPI row on top: total return, CAGR, Sharpe, Sortino, max drawdown, VaR/CVaR (95%), win rate — each with benchmark comparison.
- Equity curve vs. benchmark (buy-and-hold), with an underwater drawdown chart aligned beneath it on the same x-axis.
- Monthly returns heatmap, return distribution histogram with VaR/CVaR lines marked.
- Trades table and, for the ML signal, a SHAP feature-importance bar chart + per-signal waterfall ("why did the model say buy on 2026-03-14?").

---

## 3. Landing page

> Superseded by `docs/landing-page-plan.md` (Apple-style direction). Kept for reference.

References: **Stripe** (gradient hero + live product demo), **Linear**-style dark product sites, **Brex** (dark premium, big proof numbers), **Wise** (interactive calculator in hero), **Mercury** (real dashboard preview), **QuantConnect/Composer** (quant-specific: backtest imagery, "strategies built" counters).

Structure that consistently performs:

1. **Hero**: specific headline ("Backtest ML trading signals and see *why* the model traded"), one-line sub, **one primary CTA** ("Launch simulator") + secondary ("View on GitHub"). Right side: a *real, live* product element — best option is an interactive mini P/L curve or equity curve the visitor can drag, Wise-calculator style.
2. **Proof strip**: concrete numbers from the actual project (tickers covered, years of data, tests passing, backtests run). For a portfolio project, a GitHub/CI badge row beats fake logos.
3. **Feature bento grid** (3–5 tiles): Options chain · Strategy P/L builder · Risk analytics (VaR/CVaR/Sharpe) · Explainable signals (SHAP) · Backtester. Each tile shows a real cropped screenshot, not an icon.
4. **How it works**: the pipeline diagram (yfinance → features → XGBoost → risk → dashboard) as an animated flow.
5. **Tech/architecture section** (important for recruiters): stack, link to docs, "reproducible from public data".
6. **Footer**: disclaimer ("Simulation only — not investment advice"), GitHub, license.

Visual rules: dark navy/near-black base, one accent (blue/teal) for CTAs, green reserved for gains; Inter 40–56px bold headlines, 16–18px body at 1.6 line-height; avoid red outside loss/alert contexts.

---

## 4. Suggested frontend stack

- **Vite + React + TypeScript**, **Tailwind + shadcn/ui** (tightened: smaller padding, 0–4px radii in the app; roomier for the landing page).
- **Charts**: TradingView **lightweight-charts** for price/equity (fast canvas, familiar look); **Recharts** or **visx** for P/L curves, histograms, SHAP bars.
- **Tables**: **TanStack Table** (+ TanStack Virtual for long chains).
- **Data**: TanStack Query against the FastAPI endpoints; WebSocket later for live quotes.

---

## Sources

- tastytrade Web Platform Overview — https://support.tastytrade.com/support/s/solutions/articles/43000686118
- tastytrade Placing an Options Trade — https://support.tastytrade.com/support/s/solutions/articles/Placing-an-Options-Trade
- tastytrade Analysis mode — https://support.tastytrade.com/support/s/solutions/articles/43000435210
- TradingView Options chain overview — https://in.tradingview.com/support/solutions/43000760837
- OptionStrat (App Store listing) — https://apps.apple.com/app/id1541714905
- Best options trading platforms compared — https://www.luxalgo.com/blog/best-options-trading-platform-features-compared/
- StockBrokers.com options guide — https://www.stockbrokers.com/guides/optionstrading
- Trading platform design examples — https://merge.rocks/blog/the-10-best-trading-platform-design-examples-in-2024
- Fintech SaaS landing pages — https://designrevision.com/blog/fintech-saas-landing-pages.md
- Fintech landing page examples — https://www.saasframe.io/landing-page-examples/fintech
- Trading UI design rules — https://claudskills.com/skills/trading-design/SKILL.md
- Dashboard design examples 2026 — https://adminlte.io/blog/25-best-dashboard-design-examples-for-2026-real-products-principles/
- QuantConnect × Alpaca — https://www.quantconnect.com/brokerages/alpaca
- Composer review — https://benzinga.com/money/composer-review
