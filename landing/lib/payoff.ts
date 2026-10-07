import { greeks, price, type Greeks, type OptionType } from './blackScholes'

export interface Leg {
  type: OptionType
  /** +1 buy, -1 sell */
  side: 1 | -1
  strike: number
  qty?: number
}

export interface PricedLeg extends Required<Leg> {
  premium: number
}

export interface Market {
  spot: number
  /** years to expiry */
  T: number
  r: number
  iv: number
  /** contract multiplier: $ per index point per contract */
  multiplier: number
}

export function priceLegs(legs: Leg[], m: Market): PricedLeg[] {
  return legs.map((l) => ({
    qty: 1,
    ...l,
    premium: price(l.type, m.spot, l.strike, m.T, m.r, m.iv),
  }))
}

/** Position P/L in points per unit, `t` years before expiry (0 = at expiry). */
export function pnlAt(legs: PricedLeg[], S: number, t: number, r: number, iv: number): number {
  return legs.reduce((sum, l) => sum + l.side * l.qty * (price(l.type, S, l.strike, t, r, iv) - l.premium), 0)
}

export function priceGrid(lo: number, hi: number, n: number): number[] {
  return Array.from({ length: n }, (_, i) => lo + ((hi - lo) * i) / (n - 1))
}

export interface StrategyStats {
  /** $, negative = debit */
  netPremium: number
  /** $, null = unlimited */
  maxProfit: number | null
  /** $ (positive number), null = unlimited */
  maxLoss: number | null
  breakevens: number[]
  /** probability the position finishes in profit, under a lognormal terminal price */
  pop: number
  greeks: Greeks
}

export function strategyStats(legs: PricedLeg[], m: Market): StrategyStats {
  const wide = priceGrid(m.spot * 0.6, m.spot * 1.4, 4001)
  const ys = wide.map((S) => pnlAt(legs, S, 0, m.r, m.iv))

  // Slope at the grid edges tells us whether profit/loss keeps growing without bound.
  const n = ys.length
  const leftSlope = ys[1] - ys[0]
  const rightSlope = ys[n - 1] - ys[n - 2]
  const unboundedUp = leftSlope < -1e-6 || rightSlope > 1e-6
  const unboundedDown = leftSlope > 1e-6 || rightSlope < -1e-6

  const breakevens: number[] = []
  for (let i = 1; i < n; i++) {
    if (Math.sign(ys[i - 1]) !== Math.sign(ys[i]) && ys[i] !== 0) {
      const x = wide[i - 1] + ((wide[i] - wide[i - 1]) * -ys[i - 1]) / (ys[i] - ys[i - 1])
      breakevens.push(Math.round(x))
    }
  }

  // P(profit) = integral of the lognormal terminal density over the region where P/L > 0.
  const drift = (m.r - 0.5 * m.iv * m.iv) * m.T
  const vol = m.iv * Math.sqrt(m.T)
  let pop = 0
  let mass = 0
  for (let i = 0; i < n; i++) {
    const S = wide[i]
    const z = (Math.log(S / m.spot) - drift) / vol
    const density = Math.exp(-0.5 * z * z) / (S * vol)
    mass += density
    if (ys[i] > 0) pop += density
  }

  const net = legs.reduce(
    (g, l) => {
      const lg = greeks(l.type, m.spot, l.strike, m.T, m.r, m.iv)
      const w = l.side * l.qty * m.multiplier
      return {
        delta: g.delta + w * lg.delta,
        gamma: g.gamma + w * lg.gamma,
        theta: g.theta + w * lg.theta,
        vega: g.vega + w * lg.vega,
      }
    },
    { delta: 0, gamma: 0, theta: 0, vega: 0 },
  )

  return {
    netPremium: -legs.reduce((s, l) => s + l.side * l.qty * l.premium, 0) * m.multiplier,
    maxProfit: unboundedUp ? null : Math.max(...ys) * m.multiplier,
    maxLoss: unboundedDown ? null : -Math.min(...ys) * m.multiplier,
    breakevens,
    pop: pop / mass,
    greeks: net,
  }
}
