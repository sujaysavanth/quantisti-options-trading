import { PillButton, TextLink } from '@/components/ui/Buttons'
import { Reveal } from '@/components/ui/Reveal'
import { Section } from '@/components/ui/Section'
import { DASHBOARD_URL, GITHUB_URL, HAS_DASHBOARD } from '@/lib/links'

export function FinalCta() {
  return (
    <Section tone="dark" className="text-center">
      <Reveal className="mx-auto max-w-[760px]">
        <h2 className="text-display text-balance">Trade the week. On paper.</h2>
        <p className="mx-auto mt-5 max-w-[520px] text-lede text-balance text-muted">
          Open source, reproducible, and built end to end — from data collectors to the dashboard.
        </p>
        <div className="mt-10 flex flex-col items-center justify-center gap-5 sm:flex-row sm:gap-8">
          <PillButton href={DASHBOARD_URL}>{HAS_DASHBOARD ? 'Open dashboard' : 'Explore the code'}</PillButton>
          <TextLink href={HAS_DASHBOARD ? GITHUB_URL : `${GITHUB_URL}#readme`}>Read the docs</TextLink>
        </div>
      </Reveal>
    </Section>
  )
}
