import { useI18n } from '../i18n'

export function Grounds() {
  const { t } = useI18n()

  return (
    <section id="grounds" className="alt">
      <div className="shell">
        <div className="section-head">
          <h2>{t.grounds.title}</h2>
          <p>{t.grounds.lead}</p>
        </div>
        <div className="cards">
          {t.grounds.items.map((item) => (
            <article className="card" key={item.title}>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </article>
          ))}
        </div>
        <p className="footnote">{t.grounds.footnote}</p>
      </div>
    </section>
  )
}
