import { useEffect, useState } from 'react'
import { Header } from './components/Header'
import { Hero } from './components/Hero'
import { HowItWorks } from './components/HowItWorks'
import { Grounds } from './components/Grounds'
import { Pricing } from './components/Pricing'
import { Faq } from './components/Faq'
import { Footer } from './components/Footer'
import { fetchConfig, FALLBACK_CONFIG, type PublicConfig } from './api'

export default function App() {
  // Лендинг рендерится сразу на запасных значениях и уточняет их, когда
  // ответит бэкенд: страница не должна ждать сеть, чтобы показать текст.
  const [config, setConfig] = useState<PublicConfig>(FALLBACK_CONFIG)

  useEffect(() => {
    const controller = new AbortController()
    fetchConfig(controller.signal)
      .then(setConfig)
      .catch(() => {
        /* бэкенд не поднят — остаёмся на запасных значениях */
      })
    return () => controller.abort()
  }, [])

  return (
    <>
      <Header />
      <main>
        <Hero config={config} />
        <HowItWorks />
        <Grounds />
        <Pricing config={config} />
        <Faq />
      </main>
      <Footer />
    </>
  )
}
