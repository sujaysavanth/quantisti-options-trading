'use client'

import { motion } from 'motion/react'
import type { ReactNode } from 'react'

export const EASE = [0.25, 0.1, 0.25, 1] as const

interface RevealProps {
  children: ReactNode
  delay?: number
  className?: string
  y?: number
}

/** Fade and rise once when scrolled into view. */
export function Reveal({ children, delay = 0, className, y = 24 }: RevealProps) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '0px 0px -80px 0px' }}
      transition={{ duration: 0.7, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  )
}
