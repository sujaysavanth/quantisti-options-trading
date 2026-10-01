'use client'

import { motion } from 'motion/react'
import { Fragment } from 'react'
import { Eyebrow, Headline, Lede, Section } from '@/components/ui/Section'
import { EASE, Reveal } from '@/components/ui/Reveal'
import { chain, expiries, market, pcr } from '@/data/showcase'
import { num, pc, pct } from '@/lib/format'

const maxOi = Math.max(...chain.flatMap((r) => [r.call.oi, r.put.oi]))
const thousands = (v: number) => `${(v / 1e3).toFixed(1)}K`

const callouts = [
  { title: 'Greeks on every strike.', body: 'Delta, gamma, theta and vega from Black-Scholes, recomputed as spot moves.' },
  { title: 'Volatility with a smile.', body: 'Per-strike implied volatility and IV for each weekly and monthly expiry.' },
  { title: 'Positioning at a glance.', body: `Open interest bars and a live put-call ratio — ${pcr.toFixed(2)} this week.` },
]

export function ChainShowcase() {
  return (
    <Section id="chain" tone="light">
      <div className="mx-auto max-w-[980px] text-center">
        <Reveal>
          <Eyebrow>Option chain</Eyebrow>
          <Headline className="mt-3">Every strike. At a glance.</Headline>
          <Lede className="mx-auto mt-5 max-w-[640px]">
            Calls on the left, puts on the right, the market in the middle. In-the-money strikes shaded, spot marked where it sits.
          </Lede>
        </Reveal>
      </div>

      <motion.div
        initial={{ opacity: 0, scale: 0.92, y: 40 }}
        whileInView={{ opacity: 1, scale: 1, y: 0 }}
        viewport={{ once: true, margin: '0px 0px -15% 0px' }}
        transition={{ duration: 1, ease: EASE }}
        className="mx-auto mt-16 max-w-[1100px] md:mt-20"
      >
        <div className="overflow-hidden rounded-tile bg-white shadow-[0_30px_80px_-20px_rgba(0,0,0,0.25)]">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-black/5 px-5 py-4 md:px-8">
            <div>
              <p className="font-semibold">SPX</p>
              <p className="tabular text-sm text-muted">
                {num(market.spot)} · IV {pct(market.iv, 1)} · PCR {pcr.toFixed(2)}
              </p>
            </div>
            <div className="flex gap-2 overflow-x-auto" role="list" aria-label="Expiries">
              {expiries.map((e) => (
                <span
                  role="listitem"
                  key={e.label}
                  className={`tabular whitespace-nowrap rounded-full px-3 py-1.5 text-xs ${e.active ? 'bg-ink text-white' : 'bg-black/5 text-ink/70'}`}
                >
                  {e.label} · {e.dte}d{e.monthly ? ' · M' : ''}
                </span>
              ))}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="tabular w-full text-right text-[13px] md:text-sm">
              <caption className="sr-only">SPX option chain, Friday weekly expiry</caption>
              <thead className="text-xs text-muted">
                <tr>
                  <th colSpan={4} scope="colgroup" className="px-3 pb-1 pt-4 text-center font-semibold uppercase tracking-wider text-ink/80 md:px-4">
                    Calls
                  </th>
                  <th />
                  <th colSpan={4} scope="colgroup" className="px-3 pb-1 pt-4 text-center font-semibold uppercase tracking-wider text-ink/80 md:px-4">
                    Puts
                  </th>
                </tr>
                <tr className="border-b border-black/5">
                  <Th className="hidden md:table-cell">OI</Th>
                  <Th className="hidden md:table-cell">IV</Th>
                  <Th>Δ</Th>
                  <Th>LTP</Th>
                  <Th className="bg-black/[0.03] text-center text-ink">Strike</Th>
                  <Th>LTP</Th>
                  <Th>Δ</Th>
                  <Th className="hidden md:table-cell">IV</Th>
                  <Th className="hidden md:table-cell">OI</Th>
                </tr>
              </thead>
              <tbody>
                {chain.map((row, i) => {
                  const callItm = row.strike < market.spot
                  const putItm = row.strike > market.spot
                  const spotBefore = i > 0 && chain[i - 1].strike < market.spot && row.strike >= market.spot
                  const itm = 'bg-[#0071e3]/[0.06]'
                  return (
                    <Fragment key={row.strike}>
                      {spotBefore && (
                        <tr aria-label={`Spot ${num(market.spot)}`}>
                          <td colSpan={9} className="relative h-0 p-0">
                            <div className="absolute inset-x-0 top-0 h-px bg-[#0071e3]" />
                            <span className="absolute left-1/2 top-0 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#0071e3] px-2.5 py-0.5 text-[11px] font-semibold text-white">
                              {num(market.spot)}
                            </span>
                          </td>
                        </tr>
                      )}
                      <tr className="border-b border-black/[0.04] last:border-0">
                        <OiCell value={row.call.oi} side="call" className={callItm ? itm : ''} />
                        <Td className={`hidden md:table-cell ${callItm ? itm : ''}`}>{pct(row.call.iv, 1)}</Td>
                        <Td className={callItm ? itm : ''}>{row.call.delta.toFixed(2)}</Td>
                        <Td className={`font-medium ${callItm ? itm : ''}`}>{num(row.call.ltp, 2)}</Td>
                        <Td className="bg-black/[0.03] text-center font-semibold">{num(row.strike)}</Td>
                        <Td className={`font-medium ${putItm ? itm : ''}`}>{num(row.put.ltp, 2)}</Td>
                        <Td className={putItm ? itm : ''}>{row.put.delta.toFixed(2)}</Td>
                        <Td className={`hidden md:table-cell ${putItm ? itm : ''}`}>{pct(row.put.iv, 1)}</Td>
                        <OiCell value={row.put.oi} side="put" className={putItm ? itm : ''} />
                      </tr>
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </motion.div>

      <div className="mx-auto mt-16 grid max-w-[980px] gap-10 md:mt-24 md:grid-cols-3">
        {callouts.map((c, i) => (
          <Reveal key={c.title} delay={i * 0.08}>
            <h3 className="text-xl font-semibold tracking-tight">{c.title}</h3>
            <p className="mt-2 text-muted">{c.body}</p>
          </Reveal>
        ))}
      </div>
    </Section>
  )
}

function Th({ children, className = '' }: { children?: React.ReactNode; className?: string }) {
  return (
    <th scope="col" className={`px-3 py-2 font-medium md:px-4 ${className}`}>
      {children}
    </th>
  )
}

function Td({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-3 py-2.5 md:px-4 ${className}`}>{children}</td>
}

function OiCell({ value, side, className = '' }: { value: number; side: 'call' | 'put'; className?: string }) {
  return (
    <td className={`relative hidden px-3 py-2.5 md:table-cell md:px-4 ${className}`}>
      <span
        aria-hidden
        className={`absolute bottom-1 h-[3px] rounded-full bg-ink/15 ${side === 'call' ? 'right-3 md:right-4' : 'left-3 md:left-4'}`}
        style={{ width: pc((value / maxOi) * 0.75) }}
      />
      <span className="relative">{thousands(value)}</span>
    </td>
  )
}
