'use client'

import { motion } from 'motion/react'
import { useId, useMemo, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { inr, num, pc } from '@/lib/format'
import { EASE } from '@/components/ui/Reveal'

const W = 1000

interface PayoffChartProps {
  /** Underlying prices, evenly spaced. */
  xs: number[]
  /** P/L at expiry in ₹ for each x. Arrays of equal length morph smoothly when swapped. */
  ys: number[]
  /** Optional P/L before expiry, drawn dashed. */
  today?: number[]
  domain: [number, number]
  spot: number
  breakevens?: number[]
  height?: number
  /** Tailwind aspect classes for the plot area; the SVG stretches to fill it. */
  aspectClass?: string
  interactive?: boolean
  drawIn?: boolean
  showAxis?: boolean
  label: string
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

export function PayoffChart({
  xs,
  ys,
  today,
  domain,
  spot,
  breakevens = [],
  height = 420,
  aspectClass = 'aspect-[1000/640] md:aspect-[1000/420]',
  interactive = false,
  drawIn = false,
  showAxis = true,
  label,
}: PayoffChartProps) {
  const uid = useId().replace(/:/g, '')
  const [x0, x1] = [xs[0], xs[xs.length - 1]]
  const [d0, d1] = domain
  const H = height

  const sx = (price: number) => ((price - x0) / (x1 - x0)) * W
  const sy = (pl: number) => H - ((clamp(pl, d0, d1) - d0) / (d1 - d0)) * H
  const zeroY = sy(0)

  const { line, area, todayLine } = useMemo(() => {
    const pts = (vals: number[]) => vals.map((v, i) => `${sx(xs[i]).toFixed(1)} ${sy(v).toFixed(1)}`)
    const p = pts(ys)
    return {
      line: `M${p.join(' L')}`,
      area: `M0 ${zeroY.toFixed(1)} L${p.join(' L')} L${W} ${zeroY.toFixed(1)} Z`,
      todayLine: today ? `M${pts(today).join(' L')}` : null,
    }
    // sx/sy are pure functions of the deps below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [xs, ys, today, d0, d1, H])

  const [probe, setProbe] = useState<number | null>(null)
  const shown = probe ?? spot
  const plAt = (price: number) => {
    const t = ((price - x0) / (x1 - x0)) * (xs.length - 1)
    const i = clamp(Math.floor(t), 0, xs.length - 2)
    return ys[i] + (ys[i + 1] - ys[i]) * (t - i)
  }
  const shownPl = plAt(shown)

  const onPointer = (e: PointerEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const f = clamp((e.clientX - rect.left) / rect.width, 0, 1)
    setProbe(x0 + f * (x1 - x0))
  }
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? 250 : 50
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      e.preventDefault()
      setProbe((p) => clamp((p ?? spot) + (e.key === 'ArrowRight' ? step : -step), x0, x1))
    } else if (e.key === 'Escape') {
      setProbe(null)
    }
  }

  const ticks = xs.filter((x) => x % 500 === 0)
  const pctX = (price: number) => pc(sx(price) / W)
  const pctY = (pl: number) => pc(sy(pl) / H)
  const transition = { duration: 0.9, ease: EASE }

  return (
    <figure className="w-full select-none">
      <div
        className={`relative w-full ${aspectClass} ${interactive ? 'cursor-crosshair touch-pan-y' : ''}`}
        {...(interactive && {
          onPointerMove: onPointer,
          onPointerDown: onPointer,
          onPointerLeave: () => setProbe(null),
          onKeyDown: onKey,
          tabIndex: 0,
          role: 'slider',
          'aria-label': `${label}: move the underlying price`,
          'aria-valuemin': Math.round(x0),
          'aria-valuemax': Math.round(x1),
          'aria-valuenow': Math.round(shown),
          'aria-valuetext': `NIFTY ${num(shown)}, P/L at expiry ${inr(shownPl, true)}`,
        })}
      >
        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          className="absolute inset-0 h-full w-full overflow-visible"
          role="img"
          aria-label={label}
        >
          <defs>
            <clipPath id={`above-${uid}`}>
              <rect x="0" y="0" width={W} height={zeroY} />
            </clipPath>
            <clipPath id={`below-${uid}`}>
              <rect x="0" y={zeroY} width={W} height={H - zeroY} />
            </clipPath>
            <clipPath id={`reveal-${uid}`}>
              <motion.rect
                x="0"
                y="-20"
                height={H + 40}
                initial={{ width: drawIn ? 0 : W }}
                animate={{ width: W }}
                transition={{ duration: 1.8, ease: [0.65, 0, 0.35, 1], delay: 0.3 }}
              />
            </clipPath>
          </defs>

          <line x1="0" x2={W} y1={zeroY} y2={zeroY} stroke="currentColor" strokeOpacity="0.25" strokeDasharray="4 6" vectorEffect="non-scaling-stroke" />

          <g clipPath={`url(#reveal-${uid})`}>
            <motion.path initial={false} animate={{ d: area }} transition={transition} fill="var(--gain)" fillOpacity="0.16" clipPath={`url(#above-${uid})`} />
            <motion.path initial={false} animate={{ d: area }} transition={transition} fill="var(--loss)" fillOpacity="0.16" clipPath={`url(#below-${uid})`} />
            {todayLine && (
              <motion.path
                initial={false}
                animate={{ d: todayLine }}
                transition={transition}
                fill="none"
                stroke="currentColor"
                strokeOpacity="0.45"
                strokeWidth="1.5"
                strokeDasharray="5 6"
                vectorEffect="non-scaling-stroke"
              />
            )}
            <motion.path
              initial={false}
              animate={{ d: line }}
              transition={transition}
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinejoin="round"
              vectorEffect="non-scaling-stroke"
            />
          </g>
        </svg>

        {/* Breakevens on the zero line */}
        {breakevens
          .filter((b) => b > x0 && b < x1)
          .map((b) => (
            <span key={b} aria-hidden className="absolute h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-current opacity-60" style={{ left: pctX(b), top: pctY(0) }} />
          ))}

        {/* Probe: follows the pointer, rests on spot */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 transition-transform duration-150 ease-out will-change-transform"
          style={{ transform: `translateX(${pctX(shown)})` }}
        >
          <div className="absolute inset-y-0 left-0 w-px -translate-x-1/2 bg-current opacity-20" />
          <div className="absolute inset-0 transition-transform duration-150 ease-out" style={{ transform: `translateY(${pctY(shownPl)})` }}>
            <div
              className="absolute left-0 top-0 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-current"
              style={{ background: shownPl >= 0 ? 'var(--gain)' : 'var(--loss)' }}
            />
          </div>
          {interactive && (
            <div
              className={`absolute left-0 top-0 whitespace-nowrap rounded-xl bg-white/10 px-3 py-2 text-left backdrop-blur-md ${sx(shown) > W * 0.7 ? '-translate-x-full -ml-3' : 'ml-3'}`}
            >
              <div className="tabular text-xs text-muted">NIFTY {num(shown)}</div>
              <div className="tabular text-lg font-semibold" style={{ color: shownPl >= 0 ? 'var(--gain)' : 'var(--loss)' }}>
                {inr(shownPl, true)}
              </div>
            </div>
          )}
        </div>
      </div>

      {showAxis && (
        <div aria-hidden className="relative mt-3 h-5 text-xs text-muted">
          {ticks.map((t) => (
            <span key={t} className="tabular absolute -translate-x-1/2" style={{ left: pctX(t) }}>
              {num(t)}
            </span>
          ))}
        </div>
      )}
    </figure>
  )
}
