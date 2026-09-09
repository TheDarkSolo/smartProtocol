import { useI18n } from '../i18n'

export function HowItWorks() {
  const { t } = useI18n()

  return (
    <section id="how">
      <div className="shell">
        <div className="section-head">
          <h2>{t.how.title}</h2>
          <p>{t.how.lead}</p>
        </div>
        <ol className="steps">
          {t.how.steps.map((step) => (
            <li className="step" key={step.title}>
              <span className="step-num" aria-hidden="true" />
              <div>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
