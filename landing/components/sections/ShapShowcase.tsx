'use client'

import { motion } from 'motion/react'
import { EASE, Reveal } from '@/components/ui/Reveal'
import { Eyebrow, Headline, Lede, Section } from '@/components/ui/Section'
import { shap, shapOutput } from '@/data/showcase'
import { pc, pct } from '@/lib/format'

const D0 = 0.3
const D1 = 1
const at = (v: number) => pc((v - D0) / (D1 - D0))
const span = (v: number) => pc(Math.abs(v) / (D1 - D0))

const UP = '#0071e3'
const DOWN = '#bf4800'

// Cumulative position of each contribution, in the order the model adds them.
let running = shap.base
const rows = shap.features.map((f) => {
  const start = running
  running += f.impact
  return { ...f, from: Math.min(start, running) }
})

export function ShapShowcase() {
  return (
    <Section id="signals" tone="light">
      <div className="mx-auto max-w-[980px] text-center">
        <Reveal>
          <Eyebrow>Explainable signals</Eyebrow>
          <Headline className="mt-3">The model shows its work.</Headline>
          <Lede className="mx-auto mt-5 max-w-[640px]">
            Every prediction comes with its SHAP breakdown — which inputs pushed the call, by how much, and in which direction.
          </Lede>
        </Reveal>
      </div>

      <Reveal className="mx-auto mt-16 max-w-[980px] md:mt-20">
        <div className="rounded-tile bg-white p-6 shadow-[0_30px_80px_-30px_rgba(0,0,0,0.2)] md:p-10">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-semibold">{shap.question}</p>
            <p className="tabular text-sm text-muted">
              Base rate {pct(shap.base)} → <span className="font-semibold text-ink">{pct(shapOutput)}</span>
            </p>
          </div>

          <ul className="mt-8 space-y-3">
            {rows.map((r, i) => (
              <li key={r.name} className="grid grid-cols-[minmax(0,7.5rem)_1fr] items-center gap-4 md:grid-cols-[14rem_1fr]">
                <div className="text-sm">
                  <span className="block truncate font-medium">{r.name}</span>
                  <span className="tabular text-muted">{r.value}</span>
                </div>
                <div className="relative h-8">
                  <motion.div
                    className="absolute inset-y-0 flex items-center rounded-md"
                    style={{
                      left: at(r.from),
                      width: span(r.impact),
                      background: r.impact > 0 ? UP : DOWN,
                      transformOrigin: r.impact > 0 ? 'left' : 'right',
                    }}
                    initial={{ scaleX: 0 }}
                    whileInView={{ scaleX: 1 }}
                    viewport={{ once: true, margin: '0px 0px -60px 0px' }}
                    transition={{ duration: 0.7, ease: EASE, delay: 0.2 + i * 0.12 }}
                  />
                  <motion.span
                    className="tabular absolute top-1/2 -translate-y-1/2 whitespace-nowrap px-2 text-xs font-semibold"
                    style={r.impact > 0 ? { left: `calc(${at(r.from)} + ${span(r.impact)})`, color: UP } : { right: `calc(100% - ${at(r.from)})`, color: DOWN }}
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.4, delay: 0.7 + i * 0.12 }}
                  >
                    {r.impact > 0 ? '+' : '−'}
                    {Math.abs(r.impact * 100).toFixed(0)} pts
                  </motion.span>
                </div>
              </li>
            ))}
          </ul>

          <div aria-hidden className="mt-4 grid grid-cols-[minmax(0,7.5rem)_1fr] gap-4 md:grid-cols-[14rem_1fr]">
            <span />
            <div className="tabular relative h-4 border-t border-black/10 text-[11px] text-muted">
              {[0.4, 0.6, 0.8, 1].map((t) => (
                <span key={t} className="absolute top-1 -translate-x-1/2" style={{ left: at(t) }}>
                  {pct(t)}
                </span>
              ))}
            </div>
          </div>
        </div>
        <p className="mt-4 text-center text-xs text-muted">Illustrative explanation for a single weekly prediction.</p>
      </Reveal>
    </Section>
  )
}
