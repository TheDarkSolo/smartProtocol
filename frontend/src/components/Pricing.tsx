import { useI18n, fill } from '../i18n'
import type { PublicConfig } from '../api'
import { IconCheck } from './icons'

/** 42 000 ₸ — порядок типичного штрафа за проезд на запрещающий сигнал.
 *  Это иллюстрация, а не юридическое утверждение о размере санкции. */
const TYPICAL_FINE_KZT = 42000

function tenge(value: number): string {
  return value.toLocaleString('ru-RU').replace(/ /g, ' ')
}

export function Pricing({ config }: { config: PublicConfig }) {
  const { t } = useI18n()

  return (
    <section id="price">
      <div className="shell">
        <div className="section-head">
          <h2>{t.pricing.title}</h2>
          <p>{t.pricing.lead}</p>
        </div>

        <div className="plans">
          <div className="plan">
            <h3>{t.pricing.freeTitle}</h3>
            <div className="plan-price">{t.pricing.free}</div>
            <ul>
              {t.pricing.freeItems.map((item) => (
                <li key={item}>
                  <IconCheck />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="plan plan-featured">
            <h3>{t.pricing.paidTitle}</h3>
            <div className="plan-price">{tenge(config.document_price_kzt)} ₸</div>
            <ul>
              {t.pricing.paidItems.map((item) => (
                <li key={item}>
                  <IconCheck />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
            <a className="btn" href="#top">
              {t.pricing.cta}
            </a>
          </div>
        </div>

        <p className="compare">
          {fill(t.pricing.compare, { fine: tenge(TYPICAL_FINE_KZT) })}
        </p>
      </div>
    </section>
  )
}
