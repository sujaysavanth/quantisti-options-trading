'use client'

import { motion } from 'motion/react'
import { CountUp } from '@/components/ui/CountUp'
import { EASE, Reveal } from '@/components/ui/Reveal'
import { Eyebrow, Headline, Lede, Section } from '@/components/ui/Section'
import { risk, weeklyReturns } from '@/data/showcase'
import { num, pc, pct } from '@/lib/format'

const BIN = 0.005
const LO = -0.12
const HI = 0.04
const bins = Array.from({ length: Math.round((HI - LO) / BIN) }, (_, i) => ({ from: LO + i * BIN, count: 0 }))
for (const r of weeklyReturns) {
  const i = Math.min(bins.length - 1, Math.max(0, Math.floor((r - LO) / BIN)))
  bins[i].count++
}
const peak = Math.max(...bins.map((b) => b.count))
const at = (r: number) => pc((r - LO) / (HI - LO))

const metrics = [
  { label: 'Sharpe ratio', value: risk.sharpe, format: (v: number) => num(v, 2) },
  { label: 'Sortino ratio', value: risk.sortino, format: (v: number) => num(v, 2) },
  { label: 'Win rate', value: risk.winRate, format: (v: number) => pct(v) },
  { label: 'VaR 95%, weekly', value: risk.var95, format: (v: number) => pct(-v, 1) },
  { label: 'CVaR 95%, weekly', value: risk.cvar95, format: (v: number) => pct(-v, 1) },
  { label: 'Max drawdown', value: risk.maxDrawdown, format: (v: number) => pct(-v, 1) },
]

export function RiskShowcase() {
  return (
    <Section id="risk" tone="dark">
      <div className="mx-auto max-w-[980px] text-center">
        <Reveal>
          <Eyebrow>Risk analytics</Eyebrow>
          <Headline className="mt-3">Know your downside. Before it knows you.</Headline>
          <Lede className="mx-auto mt-5 max-w-[640px]">
            Every backtest reports the full distribution — not just the average. Tail risk is measured, marked and priced in.
          </Lede>
        </Reveal>
      </div>

      <div className="mx-auto mt-16 max-w-[1100px] md:mt-24">
        <div className="relative h-[260px] md:h-[340px]" role="img" aria-label={`Histogram of ${weeklyReturns.length} weekly returns. 95% VaR ${pct(-risk.var95, 1)}, CVaR ${pct(-risk.cvar95, 1)}.`}>
          <motion.div
            className="absolute inset-0 flex items-end gap-[2px] md:gap-1"
            initial="hidden"
            whileInView="shown"
            viewport={{ once: true, margin: '0px 0px -20% 0px' }}
          >
            {bins.map((b, i) => {
              const tail = b.from + BIN <= -risk.var95 + 1e-9
              return (
                <motion.div
                  key={i}
                  className="flex-1 rounded-t-[3px]"
                  style={{
                    height: pc(b.count / peak),
                    background: tail ? 'var(--loss)' : b.from >= 0 ? 'rgba(245,245,247,0.85)' : 'rgba(245,245,247,0.35)',
                    transformOrigin: 'bottom',
                  }}
                  variants={{ hidden: { scaleY: 0 }, shown: { scaleY: 1 } }}
                  transition={{ duration: 0.8, ease: EASE, delay: i * 0.02 }}
                />
              )
            })}
          </motion.div>

          <Marker at={at(-risk.cvar95)} label="CVaR" value={pct(-risk.cvar95, 1)} delay={1.1} top />
          <Marker at={at(-risk.var95)} label="VaR 95%" value={pct(-risk.var95, 1)} delay={0.9} />
          <div aria-hidden className="absolute inset-y-0 w-px bg-white/30" style={{ left: at(0) }} />
        </div>

        <div aria-hidden className="tabular relative mt-3 h-4 text-xs text-muted">
          {[-0.12, -0.08, -0.04, 0, 0.04].map((t, i, all) => (
            <span key={t} className={`absolute ${i === 0 ? '' : i === all.length - 1 ? '-translate-x-full' : '-translate-x-1/2'}`} style={{ left: at(t) }}>
              {pct(t, 0, true)}
            </span>
          ))}
        </div>

        <dl className="mt-16 grid grid-cols-2 gap-x-6 gap-y-10 text-center md:mt-24 md:grid-cols-3">
          {metrics.map((m) => (
            <div key={m.label} className="flex flex-col-reverse">
              <dt className="mt-2 text-sm text-muted">{m.label}</dt>
              <dd className="text-[40px] font-semibold leading-none tracking-tight md:text-[56px]">
                <CountUp value={m.value} format={m.format} />
              </dd>
            </div>
          ))}
        </dl>
        <p className="mt-12 text-center text-xs text-muted">
          Illustrative three-year weekly backtest ({weeklyReturns.length} trades) of a rules-based iron condor.
        </p>
      </div>
    </Section>
  )
}

function Marker({ at: left, label, value, delay, top }: { at: string; label: string; value: string; delay: number; top?: boolean }) {
  return (
    <motion.div
      className="absolute inset-y-0"
      style={{ left }}
      initial={{ opacity: 0, x: -24 }}
      whileInView={{ opacity: 1, x: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.6, ease: EASE, delay }}
    >
      <div className="absolute inset-y-0 w-px border-l border-dashed border-loss" />
      <div className={`absolute left-2 whitespace-nowrap text-xs ${top ? 'top-0' : 'top-10'}`}>
        <span className="block text-muted">{label}</span>
        <span className="tabular font-semibold text-loss">{value}</span>
      </div>
    </motion.div>
  )
}
