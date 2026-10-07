'use client'

import { animate, useInView, useReducedMotion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'

interface CountUpProps {
  value: number
  format: (v: number) => string
  duration?: number
  className?: string
}

/** Counts from zero to `value` the first time it scrolls into view; re-tweens when `value` changes. */
export function CountUp({ value, format, duration = 1.2, className }: CountUpProps) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true, margin: '0px 0px -60px 0px' })
  const reduced = useReducedMotion()
  const current = useRef(0)
  // Callers pass inline formatters; keep the latest one without restarting the tween.
  const formatRef = useRef(format)
  formatRef.current = format
  // Always start from zero so server and client markup match.
  const [text, setText] = useState(() => format(0))

  useEffect(() => {
    if (!inView) return
    if (reduced) {
      current.current = value
      setText(formatRef.current(value))
      return
    }
    const controls = animate(current.current, value, {
      duration,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => {
        current.current = v
        setText(formatRef.current(v))
      },
    })
    return () => controls.stop()
  }, [inView, value, duration, reduced])

  return (
    <span ref={ref} className={`tabular ${className ?? ''}`}>
      {text}
    </span>
  )
}
