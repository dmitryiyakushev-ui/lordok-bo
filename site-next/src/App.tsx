import { FinalCta, Footer, Nav } from './components/Chrome'
import { Hero } from './components/Hero'
import {
  Author,
  ForDoctors,
  HowItWorks,
  Price,
  Problem,
  Triage,
} from './components/Sections'

export default function App() {
  return (
    <>
      <Nav />
      <main id="main">
        <Hero />
        <Problem />
        <HowItWorks />
        <Triage />
        <ForDoctors />
        <Author />
        <Price />
        <FinalCta />
      </main>
      <Footer />
    </>
  )
}
