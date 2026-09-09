import { useI18n } from '../i18n'
import type { PublicConfig } from '../api'
import { UploadCard } from './UploadCard'
import { IconClock } from './icons'

export function Hero({ config }: { config: PublicConfig }) {
  const { t } = useI18n()

  return (
    <section className="hero" id="top">
      <div className="shell hero-grid">
        <div>
          <span className="eyebrow">{t.tagline}</span>
          <h1>{t.hero.title}</h1>
          <p className="hero-lead">{t.hero.lead}</p>
          <p className="hero-note">
            <IconClock />
            <span>{t.hero.note}</span>
          </p>
        </div>
        <UploadCard config={config} />
      </div>
    </section>
  )
}
