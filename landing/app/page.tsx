import { Bento } from '@/components/sections/Bento'
import { ChainShowcase } from '@/components/sections/ChainShowcase'
import { FinalCta } from '@/components/sections/FinalCta'
import { Footer } from '@/components/sections/Footer'
import { Hero } from '@/components/sections/Hero'
import { Nav } from '@/components/sections/Nav'
import { PipelineScene } from '@/components/sections/PipelineScene'
import { RangeScene } from '@/components/sections/RangeScene'
import { RiskShowcase } from '@/components/sections/RiskShowcase'
import { ShapShowcase } from '@/components/sections/ShapShowcase'
import { Specs } from '@/components/sections/Specs'
import { StrategyScene } from '@/components/sections/StrategyScene'

export default function Home() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <RangeScene />
        <ChainShowcase />
        <StrategyScene />
        <ShapShowcase />
        <RiskShowcase />
        <PipelineScene />
        <Bento />
        <Specs />
        <FinalCta />
      </main>
      <Footer />
    </>
  )
}
