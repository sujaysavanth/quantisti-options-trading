'use client'

import { AnimatePresence, motion, useMotionValue, useMotionValueEvent, useReducedMotion, useTransform, type MotionValue } from 'motion/react'
import { useState } from 'react'
import { Section } from '@/components/ui/Section'
import { ramp, StickyScene } from '@/components/ui/StickyScene'
import { EASE } from '@/components/ui/Reveal'
import { history, market, prediction } from '@/data/showcase'
import { num, pc, pct } from '@/lib/format'

const W = 1000
const H = 400
const FUTURE = prediction.horizonDays
// Each forecast session gets three slots so the band reads as a region, not a sliver.
const N = history.length + FUTURE * 3

const lo = Math.min(...history, prediction.lower) - 150
const hi = Math.max(...history, prediction.upper) + 150
const sx = (i: number) => (i / (N - 1)) * W
const sy = (v: number) => H - ((v - lo) / (hi - lo)) * H

const linePath = `M${history.map((v, i) => `${sx(i).toFixed(1)} ${sy(v).toFixed(1)}`).join(' L')}`
const lastX = sx(history.length - 1)
const bandTop = sy(prediction.upper)
const bandBottom = sy(prediction.lower)
const closeX = (lastX + W) / 2 + (W - lastX) * 0.15

const steps = [
  { title: 'Sixty sessions of NIFTY.', body: 'Daily candles, realised volatility and open interest feed a weekly feature set.' },
  { title: 'The model draws the week’s range.', body: `A ${pct(prediction.confidence)}-confidence band for the next ${FUTURE} sessions, before a single trade is placed.` },
  { title: 'And calls the close.', body: 'A point estimate for expiry day, used to rank every strategy by fit.' },
]

export function RangeScene() {
  return (
    <Section id="range" tone="dark" padded={false}>
      <StickyScene height="220vh" className="px-4 pt-20 sm:px-6 md:pt-24">
        {(progress) => <Stage progress={progress} />}
      </StickyScene>
    </Section>
  )
}

function Stage({ progress }: { progress: MotionValue<number> }) {
  const reduced = useReducedMotion()
  const done = useMotionValue(1)
  const p = reduced ? done : progress

  const [step, setStep] = useState(0)
  useMotionValueEvent(progress, 'change', (v) => setStep(v < 0.38 ? 0 : v < 0.68 ? 1 : 2))

  // A black cover over the unrevealed line shrinks toward the right: a compositor-only transform, unlike animating an SVG clip.
  const cover = useTransform(p, (v) => ramp(v, 0.02, 0.36, 1, 0))
  const bandOpacity = useTransform(p, (v) => ramp(v, 0.38, 0.55))
  const bandScale = useTransform(p, (v) => ramp(v, 0.38, 0.6, 0.15, 1))
  const closeOpacity = useTransform(p, (v) => ramp(v, 0.68, 0.76))
  const closeScale = useTransform(p, (v) => ramp(v, 0.68, 0.78, 2.2, 1))

  const current = steps[step]

  return (
    <div className="mx-auto flex h-full w-full max-w-[1200px] flex-col">
      <div className="min-h-[190px] text-center md:min-h-[210px]">
        <p className="text-eyebrow text-muted">Weekly range prediction</p>
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.25, ease: EASE }}
          >
            <h2 className="mt-3 text-headline text-balance">{current.title}</h2>
            <p className="mx-auto mt-4 max-w-[560px] text-lede text-balance text-muted">{current.body}</p>
          </motion.div>
        </AnimatePresence>
      </div>

      <div className="relative mt-6 w-full flex-1 md:mt-10">
        <div className="relative mx-auto h-full max-h-[440px] w-full">
          <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="absolute inset-0 h-full w-full overflow-visible" role="img" aria-label={`NIFTY price history with predicted range ${num(prediction.lower)} to ${num(prediction.upper)}`}>
            <line x1={lastX} x2={lastX} y1="0" y2={H} stroke="currentColor" strokeOpacity="0.15" vectorEffect="non-scaling-stroke" />

            <path d={linePath} fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
          </svg>

          <motion.div
            aria-hidden
            className="absolute -bottom-2 -left-1 -top-2 origin-right bg-black will-change-transform"
            style={{ width: `calc(${pc(lastX / W)} + 4px)`, scaleX: cover }}
          />
          <motion.div
            aria-hidden
            className="absolute right-0 will-change-transform"
            style={{
              left: pc(lastX / W),
              top: pc(bandTop / H),
              height: pc((bandBottom - bandTop) / H),
              opacity: bandOpacity,
              scaleY: bandScale,
              background: 'linear-gradient(90deg, rgba(41,151,255,0.35), rgba(41,151,255,0.12))',
            }}
          />

          {/* Band labels and close marker live in HTML so text isn't stretched by the SVG. */}
          <motion.div aria-hidden style={{ opacity: bandOpacity }} className="absolute right-0 top-0 h-full" >
            <span className="tabular absolute right-0 -translate-y-full pb-1 text-sm text-[#2997ff]" style={{ top: pc(bandTop / H) }}>
              {num(prediction.upper)}
            </span>
            <span className="tabular absolute right-0 pt-1 text-sm text-[#2997ff]" style={{ top: pc(bandBottom / H) }}>
              {num(prediction.lower)}
            </span>
          </motion.div>
          <motion.div
            aria-hidden
            style={{ opacity: closeOpacity, scale: closeScale, left: pc(closeX / W), top: pc(sy(prediction.close) / H) }}
            className="absolute -ml-2 -mt-2 h-4 w-4 rounded-full bg-white shadow-[0_0_0_6px_rgba(255,255,255,0.15)]"
          />
          <motion.span
            aria-hidden
            style={{ opacity: closeOpacity, top: pc(sy(prediction.close) / H), right: pc(1 - closeX / W) }}
            className="tabular absolute -translate-y-1/2 pr-5 text-sm font-semibold"
          >
            {num(prediction.close)}
          </motion.span>
        </div>
      </div>

      <dl className="grid grid-cols-3 gap-4 border-t border-white/10 py-6 text-center md:py-8">
        <div>
          <dt className="text-xs text-muted md:text-sm">Spot</dt>
          <dd className="tabular text-lg font-semibold md:text-2xl">{num(market.spot)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted md:text-sm">Predicted range</dt>
          <dd className="tabular text-lg font-semibold md:text-2xl">
            {num(prediction.lower)}–{num(prediction.upper)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted md:text-sm">Confidence</dt>
          <dd className="tabular text-lg font-semibold md:text-2xl">{pct(prediction.confidence)}</dd>
        </div>
      </dl>
    </div>
  )
}
