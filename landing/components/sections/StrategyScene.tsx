'use client'

import { AnimatePresence, motion, useMotionValueEvent, type MotionValue } from 'motion/react'
import { useState } from 'react'
import { PayoffChart } from '@/components/charts/PayoffChart'
import { CountUp } from '@/components/ui/CountUp'
import { EASE } from '@/components/ui/Reveal'
import { Section } from '@/components/ui/Section'
import { StickyScene } from '@/components/ui/StickyScene'
import { chartGrid, market, payoffDomain, strategies } from '@/data/showcase'
import { inr, num, pct } from '@/lib/format'

export function StrategyScene() {
  return (
    <Section id="strategies" tone="dark" padded={false}>
      <StickyScene height="240vh" className="justify-center px-4 pb-6 pt-14 sm:px-6 md:py-16">
        {(progress) => <Stage progress={progress} />}
      </StickyScene>
    </Section>
  )
}

function Stage({ progress }: { progress: MotionValue<number> }) {
  const [idx, setIdx] = useState(0)
  useMotionValueEvent(progress, 'change', (v) => setIdx(Math.min(strategies.length - 1, Math.floor(v * strategies.length))))
  const s = strategies[idx]
  const credit = s.stats.netPremium >= 0

  return (
    <div className="mx-auto w-full max-w-[1200px]">
      <div className="text-center">
        <p className="hidden text-eyebrow text-muted md:block">Strategy recommendations</p>
        <h2 className="text-headline text-balance md:mt-3">One chart. Every strategy.</h2>
      </div>

      <div className="mt-6 grid items-center gap-6 md:mt-14 md:grid-cols-12 md:gap-12">
        <div className="md:col-span-7">
          <PayoffChart
            xs={chartGrid}
            ys={s.expiry}
            today={s.today}
            domain={payoffDomain}
            spot={market.spot}
            breakevens={s.stats.breakevens}
            aspectClass="aspect-[1000/460] md:aspect-[1000/640]"
            label={`${s.name} payoff diagram`}
          />
        </div>

        <div className="md:col-span-5">
          <div className="flex gap-1.5 md:flex-wrap md:gap-2" role="tablist" aria-label="Strategies">
            {strategies.map((st, i) => (
              <span
                key={st.id}
                role="tab"
                aria-selected={i === idx}
                className={`whitespace-nowrap rounded-full px-2.5 py-1 text-xs transition-colors md:px-3.5 md:py-1.5 md:text-sm duration-300 ${i === idx ? 'bg-paper text-black' : 'bg-white/10 text-paper/70'}`}
              >
                {st.name}
              </span>
            ))}
          </div>

          <div className="mt-3 min-h-[96px] md:mt-8 md:min-h-[150px]" role="tabpanel">
            <AnimatePresence mode="wait">
              <motion.div
                key={s.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.25, ease: EASE }}
              >
                <p className="text-xs font-semibold uppercase tracking-wider text-[#2997ff] md:text-sm">{s.thesis}</p>
                <p className="mt-1.5 text-[15px] leading-snug text-muted md:mt-2 md:text-xl">{s.blurb}</p>
                <p className="tabular mt-3 hidden text-sm text-muted md:block">
                  {s.legs.map((l) => `${l.side > 0 ? 'Buy' : 'Sell'} ${num(l.strike)} ${l.type === 'C' ? 'CE' : 'PE'}`).join(' · ')}
                </p>
              </motion.div>
            </AnimatePresence>
          </div>

          <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-white/10 pt-4 md:mt-8 md:gap-y-6 md:pt-6">
            <Stat label={credit ? 'Net credit' : 'Net debit'}>
              <CountUp value={Math.abs(s.stats.netPremium)} format={(v) => inr(v)} duration={0.8} />
            </Stat>
            <Stat label="Chance of profit">
              <CountUp value={s.stats.pop} format={(v) => pct(v)} duration={0.8} />
            </Stat>
            <Stat label="Max profit">
              {s.stats.maxProfit === null ? <span>Unlimited</span> : <CountUp value={s.stats.maxProfit} format={(v) => inr(v)} duration={0.8} className="text-gain" />}
            </Stat>
            <Stat label="Max loss">
              {s.stats.maxLoss === null ? <span className="text-loss">Unlimited</span> : <CountUp value={s.stats.maxLoss} format={(v) => inr(v)} duration={0.8} className="text-loss" />}
            </Stat>
          </dl>
          <p className="mt-6 hidden text-xs text-muted md:block">Per lot of {market.lotSize}. Scroll to compare.</p>
        </div>
      </div>
    </div>
  )
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="mt-1 text-xl font-semibold tracking-tight md:text-[28px]">{children}</dd>
    </div>
  )
}
