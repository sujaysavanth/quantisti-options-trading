export type OptionType = 'C' | 'P'

const SQRT_2PI = Math.sqrt(2 * Math.PI)

export function normPdf(x: number): number {
  return Math.exp(-0.5 * x * x) / SQRT_2PI
}

// Abramowitz & Stegun 26.2.17, |error| < 7.5e-8
export function normCdf(x: number): number {
  const k = 1 / (1 + 0.2316419 * Math.abs(x))
  const poly =
    k * (0.31938153 + k * (-0.356563782 + k * (1.781477937 + k * (-1.821255978 + k * 1.330274429))))
  const tail = normPdf(x) * poly
  return x >= 0 ? 1 - tail : tail
}

function d1d2(S: number, K: number, T: number, r: number, iv: number) {
  const vt = iv * Math.sqrt(T)
  const d1 = (Math.log(S / K) + (r + 0.5 * iv * iv) * T) / vt
  return { d1, d2: d1 - vt }
}

/** European option price. T in years; at or after expiry returns intrinsic value. */
export function price(type: OptionType, S: number, K: number, T: number, r: number, iv: number): number {
  if (T <= 0) return type === 'C' ? Math.max(S - K, 0) : Math.max(K - S, 0)
  const { d1, d2 } = d1d2(S, K, T, r, iv)
  const df = Math.exp(-r * T)
  return type === 'C'
    ? S * normCdf(d1) - K * df * normCdf(d2)
    : K * df * normCdf(-d2) - S * normCdf(-d1)
}

export interface Greeks {
  delta: number
  gamma: number
  /** per calendar day */
  theta: number
  /** per 1 vol point */
  vega: number
}

export function greeks(type: OptionType, S: number, K: number, T: number, r: number, iv: number): Greeks {
  const { d1, d2 } = d1d2(S, K, T, r, iv)
  const df = Math.exp(-r * T)
  const pdf = normPdf(d1)
  const sqrtT = Math.sqrt(T)
  const gamma = pdf / (S * iv * sqrtT)
  const vega = (S * pdf * sqrtT) / 100
  const common = (-S * pdf * iv) / (2 * sqrtT)
  if (type === 'C') {
    return { delta: normCdf(d1), gamma, vega, theta: (common - r * K * df * normCdf(d2)) / 365 }
  }
  return { delta: normCdf(d1) - 1, gamma, vega, theta: (common + r * K * df * normCdf(-d2)) / 365 }
}
