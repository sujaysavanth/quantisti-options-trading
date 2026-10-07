'use client'

import { MotionConfig } from 'motion/react'

/** `reducedMotion="user"` drops transform animations for visitors who ask for less motion. */
export function Providers({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>
}
