/** CSS percentage rounded to 3 dp. Browsers round long inline-style decimals, which breaks hydration. */
export function pc(fraction: number): string {
  return `${Number((fraction * 100).toFixed(3))}%`
}

const inrFmt = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })

/** ₹12,34,567 style, with an explicit sign when `signed` is set. */
export function inr(value: number, signed = false): string {
  const sign = value < 0 ? '−' : signed && value > 0 ? '+' : ''
  return `${sign}₹${inrFmt.format(Math.abs(Math.round(value)))}`
}

export function num(value: number, digits = 0): string {
  return new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value)
}

export function pct(value: number, digits = 0, signed = false): string {
  const sign = value < 0 ? '−' : signed && value > 0 ? '+' : ''
  return `${sign}${Math.abs(value * 100).toFixed(digits)}%`
}
