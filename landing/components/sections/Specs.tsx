import { Reveal } from '@/components/ui/Reveal'
import { Eyebrow, Headline, Section } from '@/components/ui/Section'
import { specs } from '@/data/showcase'

export function Specs() {
  return (
    <Section id="tech" tone="light">
      <div className="mx-auto max-w-[980px]">
        <Reveal>
          <Eyebrow>Under the hood</Eyebrow>
          <Headline className="mt-3">Tech specs.</Headline>
        </Reveal>

        <dl className="mt-12 md:mt-16">
          {specs.map((row) => (
            <Reveal key={row.label} y={12} className="grid gap-2 border-t border-black/10 py-7 md:grid-cols-[14rem_1fr] md:gap-8">
              <dt className="text-xl font-semibold tracking-tight">{row.label}</dt>
              <dd>
                <ul className="space-y-1.5 text-[17px]">
                  {row.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </dd>
            </Reveal>
          ))}
        </dl>
      </div>
    </Section>
  )
}
