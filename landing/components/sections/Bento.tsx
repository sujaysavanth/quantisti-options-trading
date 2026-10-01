'use client'

import { PayoffChart } from '@/components/charts/PayoffChart'
import { CountUp } from '@/components/ui/CountUp'
import { Reveal } from '@/components/ui/Reveal'
import { Eyebrow, Headline, Section } from '@/components/ui/Section'
import { chartGrid, market, condorDomain, risk, services, shap, strategies } from '@/data/showcase'
import { num, pc, pct, usd } from '@/lib/format'

const condor = strategies[0]
const g = condor.stats.greeks

function Tile({ title, caption, className = '', children, delay = 0 }: { title: string; caption: string; className?: string; children: React.ReactNode; delay?: number }) {
  return (
    <Reveal delay={delay} className={`flex flex-col overflow-hidden rounded-tile bg-[#161617] p-7 md:p-9 ${className}`}>
      <p className="text-sm font-semibold text-muted">{title}</p>
      <p className="mt-2 text-2xl font-semibold leading-tight tracking-tight text-balance md:text-[28px]">{caption}</p>
      <div className="mt-8 flex flex-1 flex-col justify-end">{children}</div>
    </Reveal>
  )
}

const equityPath = (() => {
  const c = risk.curve
  const lo = Math.min(...c)
  const hi = Math.max(...c)
  return `M${c.map((v, i) => `${((i / (c.length - 1)) * 300).toFixed(1)} ${(100 - ((v - lo) / (hi - lo)) * 100).toFixed(1)}`).join(' L')}`
})()

const paperOrders = [
  { name: 'Iron Condor', legs: '7500 / 7550 / 7750 / 7800', pl: 640 },
  { name: 'Bull Call Spread', legs: '7650 / 7725', pl: -410 },
  { name: 'Short Strangle', legs: '7525 / 7775', pl: 890 },
]

export function Bento() {
  return (
    <Section id="highlights" tone="dark">
      <div className="mx-auto max-w-[1100px]">
        <Reveal className="text-center">
          <Eyebrow>Highlights</Eyebrow>
          <Headline className="mt-3">Everything a desk needs. Nothing it doesn’t.</Headline>
        </Reveal>

        <div className="mt-16 grid gap-4 md:mt-20 md:grid-cols-3 md:gap-5">
          <Tile title="Payoff" caption="See the whole trade before you place it." className="md:col-span-2">
            <PayoffChart
              xs={chartGrid}
              ys={condor.expiry}
              domain={condorDomain}
              spot={market.spot}
              breakevens={condor.stats.breakevens}
              aspectClass="aspect-[1000/380]"
              showAxis={false}
              label="Iron condor payoff thumbnail"
            />
          </Tile>

          <Tile title="Greeks" caption="Net exposure, per position." delay={0.08}>
            <dl className="tabular grid grid-cols-2 gap-5">
              {[
                ['Delta', num(g.delta, 1).replace('-', '−')],
                ['Gamma', num(g.gamma, 3).replace('-', '−')],
                ['Theta', `${usd(g.theta, true)}/d`],
                ['Vega', usd(g.vega, true)],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt className="text-xs text-muted">{k}</dt>
                  <dd className="text-xl font-semibold">{v}</dd>
                </div>
              ))}
            </dl>
          </Tile>

          <Tile title="Paper trading" caption="Practise with live quotes, not real money.">
            <ul className="space-y-3 text-sm">
              {paperOrders.map((o) => (
                <li key={o.name} className="flex items-center justify-between gap-3 rounded-xl bg-white/5 px-4 py-3">
                  <div className="min-w-0">
                    <p className="font-medium">{o.name}</p>
                    <p className="tabular truncate text-xs text-muted">{o.legs}</p>
                  </div>
                  <span className={`tabular shrink-0 font-semibold ${o.pl >= 0 ? 'text-gain' : 'text-loss'}`}>
                    {o.pl >= 0 ? '▲' : '▼'} {usd(o.pl, true)}
                  </span>
                </li>
              ))}
            </ul>
          </Tile>

          <Tile title="Backtests" caption="Three years of expiries in seconds." delay={0.08}>
            <svg viewBox="0 0 300 100" preserveAspectRatio="none" className="h-24 w-full" role="img" aria-label="Backtest equity curve">
              <path d={equityPath} fill="none" stroke="var(--gain)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
            </svg>
            <p className="tabular mt-3 text-sm text-muted">
              CAGR <span className="font-semibold text-paper"><CountUp value={risk.cagr} format={(v) => pct(v, 1)} /></span> · Sharpe{' '}
              <span className="font-semibold text-paper">{num(risk.sharpe, 2)}</span>
            </p>
          </Tile>

          <Tile title="Explainability" caption="Top reasons, in plain numbers." delay={0.16}>
            <ul className="space-y-2.5">
              {shap.features.slice(0, 4).map((f) => (
                <li key={f.name} className="flex items-center gap-3 text-sm">
                  <span className="w-28 shrink-0 truncate text-muted">{f.name}</span>
                  <span className="h-2 rounded-full" style={{ width: pc(Math.abs(f.impact) * 2.6), maxWidth: '100%', background: f.impact > 0 ? '#2997ff' : '#ff9f0a' }} />
                </li>
              ))}
            </ul>
          </Tile>

          <Tile title="Architecture" caption="Eight services. One compose file." className="md:col-span-3">
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4 md:grid-cols-8">
              {services.map((s) => (
                <li key={s.name} className="rounded-xl bg-white/5 px-4 py-3">
                  <p className="font-medium">{s.name}</p>
                  <p className="tabular font-mono text-xs text-muted">:{s.port}</p>
                </li>
              ))}
            </ul>
          </Tile>
        </div>
      </div>
    </Section>
  )
}
