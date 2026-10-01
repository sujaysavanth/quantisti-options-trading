'use client'

import { motion, useMotionValueEvent, useTransform, type MotionValue } from 'motion/react'
import { useState } from 'react'
import { Section } from '@/components/ui/Section'
import { ramp, StickyScene } from '@/components/ui/StickyScene'
import { pipeline } from '@/data/showcase'

export function PipelineScene() {
  return (
    <Section id="how" tone="light" padded={false}>
      <StickyScene height="180vh" className="justify-center px-4 py-16 sm:px-6">
        {(progress) => <Stage progress={progress} />}
      </StickyScene>
    </Section>
  )
}

function Stage({ progress }: { progress: MotionValue<number> }) {
  const n = pipeline.length
  const [active, setActive] = useState(0)
  useMotionValueEvent(progress, 'change', (v) => setActive(Math.min(n - 1, Math.floor(v * 1.15 * n))))
  const fill = useTransform(progress, (v) => ramp(v, 0, 1 / 1.15))

  return (
    <div className="mx-auto w-full max-w-[1200px]">
      <div className="text-center">
        <p className="text-eyebrow text-muted">How it works</p>
        <h2 className="mt-3 text-headline text-balance">From tick to trade.</h2>
        <p className="mx-auto mt-4 max-w-[560px] text-lede text-balance text-muted">Six stages, each its own service, each replaceable.</p>
      </div>

      <ol className="relative mx-auto mt-10 grid max-w-[420px] gap-5 md:mt-20 md:max-w-none md:grid-cols-6 md:gap-4">
        {/* Track: vertical on mobile, horizontal from md up */}
        <div aria-hidden className="absolute bottom-6 left-6 top-6 w-0.5 -translate-x-1/2 bg-black/10 md:hidden">
          <motion.div className="h-full w-full origin-top bg-ink" style={{ scaleY: fill }} />
        </div>
        <div aria-hidden className="absolute left-[8.33%] right-[8.33%] top-6 hidden h-0.5 -translate-y-1/2 bg-black/10 md:block">
          <motion.div className="h-full w-full origin-left bg-ink" style={{ scaleX: fill }} />
        </div>

        {pipeline.map((node, i) => {
          const on = i <= active
          return (
            <li key={node.name} className="relative flex items-center gap-4 md:flex-col md:text-center" aria-current={i === active ? 'step' : undefined}>
              <span
                className={`relative z-10 flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-sm font-semibold transition-colors duration-500 ${on ? 'bg-ink text-white' : 'bg-[#e8e8ed] text-muted'}`}
              >
                {i + 1}
              </span>
              <div className={`transition-opacity duration-500 ${on ? 'opacity-100' : 'opacity-40'}`}>
                <p className="text-lg font-semibold tracking-tight">{node.name}</p>
                <p className="text-sm text-muted">{node.detail}</p>
                <p className="tabular mt-1 hidden font-mono text-xs text-muted md:block">{node.port}</p>
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
