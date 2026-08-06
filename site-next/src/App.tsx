import { FinalCta, Footer, Nav } from './components/Chrome'
import { Hero } from './components/Hero'
import { WeekChart } from './components/WeekChart'
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
        <WeekChart />
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
