'use client'

import { useScroll, type MotionValue } from 'motion/react'
import { useRef, type ReactNode } from 'react'

interface StickySceneProps {
  /** Total scroll length of the scene; the stage stays pinned for (height − 100vh). */
  height?: string
  className?: string
  children: (progress: MotionValue<number>) => ReactNode
}

/**
 * Linear map of scene progress from [a, b] to [from, to], clamped.
 * Pass this to `useTransform(progress, v => ramp(...))` rather than using the
 * range-array form: Motion offloads range-array opacity to a native ViewTimeline
 * whose range ignores our `offset`, which made elements fade back out mid-scene.
 */
export function ramp(v: number, a: number, b: number, from = 0, to = 1): number {
  const t = Math.min(1, Math.max(0, (v - a) / (b - a)))
  return from + (to - from) * t
}

/** A tall section with a viewport-sized pinned stage; `progress` runs 0 → 1 while pinned. */
export function StickyScene({ height = '260vh', className = '', children }: StickySceneProps) {
  const ref = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end end'] })

  return (
    <div ref={ref} style={{ height }} className="relative">
      <div className={`sticky top-0 flex h-[100svh] flex-col overflow-hidden ${className}`}>{children(scrollYProgress)}</div>
    </div>
  )
}
