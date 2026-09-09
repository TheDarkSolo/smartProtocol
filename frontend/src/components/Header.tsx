import { useI18n } from '../i18n'
import type { Lang } from '../i18n'
import { IconLogo } from './icons'

const LANGS: { code: Lang; label: string }[] = [
  { code: 'ru', label: 'RU' },
  { code: 'kk', label: 'ҚАЗ' },
]

export function Header() {
  const { t, lang, setLang } = useI18n()

  return (
    <header className="header">
      <div className="shell header-inner">
        <a className="wordmark" href="#top">
          <span className="wordmark-mark" aria-hidden="true">
            <IconLogo />
          </span>
          {t.brand}
          <small>{t.tagline}</small>
        </a>

        <nav aria-label={t.nav.how}>
          <a href="#how">{t.nav.how}</a>
          <a href="#grounds">{t.nav.grounds}</a>
          <a href="#price">{t.nav.price}</a>
          <a href="#faq">{t.nav.faq}</a>
        </nav>

        <div className="lang">
          {LANGS.map(({ code, label }) => (
            <button
              key={code}
              type="button"
              onClick={() => setLang(code)}
              aria-pressed={lang === code}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </header>
  )
}
