/**
 * Illustrative showcase data for the landing page. Option values are computed
 * with Black-Scholes from the market parameters below so every number on the
 * page is internally consistent; the market itself is a sample, not live data.
 */
import { price, greeks } from '@/lib/blackScholes'
import { priceGrid, priceLegs, pnlAt, strategyStats, type Leg, type Market } from '@/lib/payoff'

// A Monday close (spot = SPX's 30 Sep 2026 close) valued for that week's Friday expiry.
export const market: Market = {
  spot: 7651.54,
  T: 4 / 365,
  r: 0.0425,
  iv: 0.14,
  multiplier: 100,
}

export const expiryLabel = 'Fri, 2 Oct'

// ---------------------------------------------------------------- strategies

interface StrategyDef {
  id: string
  name: string
  thesis: string
  blurb: string
  legs: Leg[]
}

const defs: StrategyDef[] = [
  {
    id: 'iron-condor',
    name: 'Iron Condor',
    thesis: 'Range-bound',
    blurb: 'Sell both wings, buy protection further out. Profits if SPX stays inside the range.',
    legs: [
      { type: 'P', side: 1, strike: 7500 },
      { type: 'P', side: -1, strike: 7550 },
      { type: 'C', side: -1, strike: 7750 },
      { type: 'C', side: 1, strike: 7800 },
    ],
  },
  {
    id: 'bull-call',
    name: 'Bull Call Spread',
    thesis: 'Moderately bullish',
    blurb: 'Buy a call, sell a higher one. Capped upside, capped risk, cheaper than a naked call.',
    legs: [
      { type: 'C', side: 1, strike: 7650 },
      { type: 'C', side: -1, strike: 7725 },
    ],
  },
  {
    id: 'short-strangle',
    name: 'Short Strangle',
    thesis: 'Low volatility',
    blurb: 'Sell an OTM call and an OTM put. Collects the most premium — and carries open-ended risk.',
    legs: [
      { type: 'P', side: -1, strike: 7525 },
      { type: 'C', side: -1, strike: 7775 },
    ],
  },
]

export const chartGrid = priceGrid(7350, 7950, 121)

export const strategies = defs.map((d) => {
  const legs = priceLegs(d.legs, market)
  const toDollars = (points: number) => points * market.multiplier
  return {
    ...d,
    legs,
    stats: strategyStats(legs, market),
    expiry: chartGrid.map((S) => toDollars(pnlAt(legs, S, 0, market.r, market.iv))),
    today: chartGrid.map((S) => toDollars(pnlAt(legs, S, market.T * 0.6, market.r, market.iv))),
  }
})

export type Strategy = (typeof strategies)[number]

/** Shared y-range so curves can morph between strategies without rescaling. */
export const payoffDomain: [number, number] = [-17000, 6000]

/** Tighter range for single-strategy charts (hero, thumbnails). */
export const condorDomain: [number, number] = [-4500, 2500]

// ---------------------------------------------------------------- option chain

const chainStrikes = priceGrid(7615, 7680, 14)

function smileIv(K: number) {
  const m = Math.log(K / market.spot)
  return market.iv - 0.6 * m + 25 * m * m
}

function openInterest(K: number, side: 'C' | 'P') {
  // SPX open interest is in contracts; it clusters at round strikes and puts carry more.
  const round = K % 100 === 0 ? 2.1 : K % 25 === 0 ? 1.4 : 1
  const skew = side === 'C' ? (K > market.spot ? 1.1 : 0.6) : K < market.spot ? 1.5 : 0.7
  const decay = Math.exp(-Math.abs(K - market.spot) / 150)
  return 4_000 * round * skew * (0.5 + decay)
}

export const chain = chainStrikes.map((K) => {
  const iv = smileIv(K)
  const c = greeks('C', market.spot, K, market.T, market.r, iv)
  const p = greeks('P', market.spot, K, market.T, market.r, iv)
  return {
    strike: K,
    call: {
      ltp: price('C', market.spot, K, market.T, market.r, iv),
      delta: c.delta,
      iv,
      oi: openInterest(K, 'C'),
    },
    put: {
      ltp: price('P', market.spot, K, market.T, market.r, iv),
      delta: p.delta,
      iv,
      oi: openInterest(K, 'P'),
    },
  }
})

export const pcr = chain.reduce((s, r) => s + r.put.oi, 0) / chain.reduce((s, r) => s + r.call.oi, 0)

// SPX lists an expiry every trading day; the chain above is the Friday weekly.
export const expiries = [
  { label: '29 Sep', dte: 1 },
  { label: '30 Sep', dte: 2 },
  { label: '1 Oct', dte: 3 },
  { label: '2 Oct', dte: 4, active: true },
  { label: '16 Oct', dte: 18, monthly: true },
]

// ---------------------------------------------------------------- seeded randomness

function mulberry32(seed: number) {
  return () => {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function gaussian(rand: () => number) {
  const u = Math.max(rand(), 1e-12)
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * rand())
}

// ---------------------------------------------------------------- weekly range prediction

const walk = mulberry32(7)
const rawHistory: number[] = [7280]
for (let i = 1; i < 60; i++) {
  rawHistory.push(rawHistory[i - 1] * (1 + 0.0006 + 0.0075 * gaussian(walk)))
}
const rescale = market.spot / rawHistory[rawHistory.length - 1]

export const history = rawHistory.map((v) => v * rescale)

const weeklySigma = market.iv * Math.sqrt(market.T)

export const prediction = {
  lower: Math.round((market.spot * (1 - 1.08 * weeklySigma)) / 10) * 10,
  upper: Math.round((market.spot * (1 + 1.08 * weeklySigma)) / 10) * 10,
  close: 7690,
  confidence: 0.72,
  horizonDays: 5,
}

// ---------------------------------------------------------------- SHAP explanation

export const shap = {
  question: 'P(week closes inside the range)',
  base: 0.41,
  features: [
    { name: 'VIX', value: '15.9', impact: 0.21 },
    { name: 'Put / call OI', value: pcr.toFixed(2), impact: 0.14 },
    { name: 'IV rank', value: '28', impact: 0.09 },
    { name: 'Days to expiry', value: '4', impact: 0.05 },
    { name: '10-day realised vol', value: '10.5%', impact: -0.04 },
    { name: '20-day trend', value: '+1.6%', impact: -0.06 },
  ],
}

export const shapOutput = shap.base + shap.features.reduce((s, f) => s + f.impact, 0)

// ---------------------------------------------------------------- backtest risk

const riskRand = mulberry32(42)
export const weeklyReturns = Array.from({ length: 156 }, () =>
  riskRand() < 0.82 ? 0.014 + 0.006 * gaussian(riskRand) : -0.04 + 0.025 * gaussian(riskRand),
)

function riskMetrics(rets: number[]) {
  const n = rets.length
  const mean = rets.reduce((s, x) => s + x, 0) / n
  const sd = Math.sqrt(rets.reduce((s, x) => s + (x - mean) ** 2, 0) / (n - 1))
  const downside = Math.sqrt(rets.reduce((s, x) => s + Math.min(x, 0) ** 2, 0) / n)
  const sorted = [...rets].sort((a, b) => a - b)
  const cut = Math.floor(0.05 * n)
  const var95 = -sorted[cut]
  const cvar95 = -sorted.slice(0, cut + 1).reduce((s, x) => s + x, 0) / (cut + 1)

  let equity = 1
  let peak = 1
  let maxDd = 0
  const curve = rets.map((r) => {
    equity *= 1 + r
    peak = Math.max(peak, equity)
    maxDd = Math.max(maxDd, 1 - equity / peak)
    return equity
  })

  return {
    sharpe: (mean / sd) * Math.sqrt(52),
    sortino: (mean / downside) * Math.sqrt(52),
    var95,
    cvar95,
    maxDrawdown: maxDd,
    winRate: rets.filter((r) => r > 0).length / n,
    cagr: equity ** (52 / n) - 1,
    curve,
  }
}

export const risk = riskMetrics(weeklyReturns)

// ---------------------------------------------------------------- architecture

export const pipeline = [
  { name: 'Collectors', detail: 'Yahoo · CBOE · FRED', port: 'scripts/' },
  { name: 'Market', detail: 'Candles, chain, Black-Scholes Greeks', port: ':8081' },
  { name: 'Stream', detail: 'Live quotes over WebSocket', port: ':8090' },
  { name: 'ML', detail: 'Weekly features, range model', port: ':8085' },
  { name: 'Simulator', detail: 'Strategies, backtests, paper trades', port: ':8082' },
  { name: 'Dashboard', detail: 'Next.js strategy desk', port: 'web' },
]

export const services = [
  { name: 'gateway', port: 8080 },
  { name: 'market', port: 8081 },
  { name: 'simulator', port: 8082 },
  { name: 'portfolio', port: 8083 },
  { name: 'stats', port: 8084 },
  { name: 'ml', port: 8085 },
  { name: 'explain', port: 8086 },
  { name: 'stream', port: 8090 },
]

export const specs: { label: string; items: string[] }[] = [
  { label: 'Services', items: ['8 FastAPI microservices', 'Health and readiness probes on every service', 'Docker Compose for local, Cloud Run for deploy'] },
  { label: 'Market data', items: ['S&P 500 daily history via Yahoo Finance', 'CBOE VIX and FRED T-bill rates', 'Daily SPX chain snapshots, Black-Scholes when none exist'] },
  { label: 'Pricing', items: ['Black-Scholes-Merton for European, cash-settled SPX', 'IV recomputed from mid quotes against a parity-implied forward', 'VIX-anchored volatility smile and NYSE expiry calendar'] },
  { label: 'Machine learning', items: ['Price, technical and volatility feature pipeline', 'XGBoost weekly range model', 'SHAP explanations per prediction'] },
  { label: 'Simulation', items: ['10+ multi-leg strategy templates', 'Asynchronous backtest engine', 'Paper trading marked to live quotes'] },
  { label: 'Risk', items: ['VaR and CVaR at 95%', 'Sharpe, Sortino, max drawdown', 'Win rate and payoff statistics'] },
  { label: 'Storage', items: ['PostgreSQL 16', 'Versioned SQL schema', 'In-memory quote store for live ticks'] },
  { label: 'Frontend', items: ['Next.js, React, TypeScript', 'Tailwind CSS', 'Motion for scroll-driven animation'] },
  { label: 'Delivery', items: ['GitHub Actions CI', 'Terraform', 'Google Cloud Run'] },
]
