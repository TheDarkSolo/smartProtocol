import { useI18n } from '../i18n'

export function Faq() {
  const { t } = useI18n()

  return (
    <section id="faq" className="alt">
      <div className="shell">
        <div className="section-head">
          <h2>{t.faq.title}</h2>
        </div>
        <div className="faq-list">
          {t.faq.items.map((item) => (
            <details className="faq-item" key={item.q}>
              <summary>{item.q}</summary>
              <p className="faq-answer">{item.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  )
}
