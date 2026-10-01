'use client'

import { motion } from 'motion/react'
import { PayoffChart } from '@/components/charts/PayoffChart'
import { PillButton, TextLink } from '@/components/ui/Buttons'
import { CountUp } from '@/components/ui/CountUp'
import { EASE } from '@/components/ui/Reveal'
import { Section } from '@/components/ui/Section'
import { chartGrid, expiryLabel, market, condorDomain, strategies } from '@/data/showcase'
import { inr, num, pct } from '@/lib/format'
import { DASHBOARD_URL, GITHUB_URL, HAS_DASHBOARD } from '@/lib/links'

const condor = strategies[0]

const rise = (delay: number) => ({
  initial: { opacity: 0, y: 24 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.9, ease: EASE, delay },
})

export function Hero() {
  const { stats } = condor

  return (
    <Section id="top" tone="dark" padded={false} className="overflow-hidden px-4 pb-24 pt-28 sm:px-6 md:pb-32 md:pt-36">
      <div className="mx-auto max-w-[980px] text-center">
        <motion.p {...rise(0)} className="text-eyebrow text-muted">
          Quantisti
        </motion.p>
        <motion.h1 {...rise(0.08)} className="mt-3 text-display text-balance">
          Options, explained.
        </motion.h1>
        <motion.p {...rise(0.16)} className="mx-auto mt-5 max-w-[640px] text-lede text-balance text-muted">
          Predict the week’s NIFTY range. Pick the strategy. See exactly why the model chose it.
        </motion.p>
        <motion.div {...rise(0.24)} className="mt-8 flex flex-col items-center justify-center gap-5 sm:flex-row sm:gap-8">
          <PillButton href={DASHBOARD_URL}>{HAS_DASHBOARD ? 'Open dashboard' : 'Explore the code'}</PillButton>
          <TextLink href="#range">See how it works</TextLink>
          {HAS_DASHBOARD && <TextLink href={GITHUB_URL}>View on GitHub</TextLink>}
        </motion.div>
      </div>

      <motion.div {...rise(0.4)} className="mx-auto mt-16 max-w-[1200px] md:mt-24">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4 px-1">
          <div>
            <p className="text-2xl font-semibold tracking-tight">{condor.name}</p>
            <p className="tabular text-sm text-muted">
              NIFTY {num(market.spot)} · expires {expiryLabel}
            </p>
          </div>
          <div className="flex items-center gap-5 text-xs text-muted">
            <span className="flex items-center gap-2">
              <span aria-hidden className="h-0.5 w-5 bg-paper" /> At expiry
            </span>
            <span className="flex items-center gap-2">
              <span aria-hidden className="w-5 border-t border-dashed border-paper/60" /> Today
            </span>
          </div>
        </div>

        <PayoffChart
          xs={chartGrid}
          ys={condor.expiry}
          today={condor.today}
          domain={condorDomain}
          spot={market.spot}
          breakevens={stats.breakevens}
          interactive
          drawIn
          label={`${condor.name} payoff diagram`}
        />
        <p className="mt-2 text-center text-xs text-muted">Drag across the chart, or focus it and use the arrow keys.</p>

        <dl className="mt-12 grid grid-cols-2 gap-x-6 gap-y-10 border-t border-white/10 pt-10 text-center md:grid-cols-4">
          <HeroStat label="Max profit">
            <CountUp value={stats.maxProfit ?? 0} format={(v) => inr(v)} className="text-gain" />
          </HeroStat>
          <HeroStat label="Max loss">
            <CountUp value={stats.maxLoss ?? 0} format={(v) => inr(v)} className="text-loss" />
          </HeroStat>
          <HeroStat label="Breakevens">
            <span className="tabular">{stats.breakevens.map((b) => num(b)).join(' – ')}</span>
          </HeroStat>
          <HeroStat label="Chance of profit">
            <CountUp value={stats.pop} format={(v) => pct(v)} />
          </HeroStat>
        </dl>
      </motion.div>
    </Section>
  )
}

function HeroStat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="mt-1 text-2xl font-semibold tracking-tight md:text-[32px]">{children}</dd>
    </div>
  )
}
