import { useI18n } from '../i18n'
import { IconLogo } from './icons'

export function Footer() {
  const { t } = useI18n()

  return (
    <footer className="footer">
      <div className="shell">
        <div className="footer-top">
          <a className="wordmark" href="#top">
            <span className="wordmark-mark" aria-hidden="true">
              <IconLogo />
            </span>
            {t.brand}
          </a>
          <nav className="footer-links">
            {/* Ссылки-заглушки: страницы обязаны появиться до приёма первого платежа. */}
            <a href="#offer">{t.footer.offer}</a>
            <a href="#privacy">{t.footer.privacy}</a>
            <a href="#contact">{t.footer.contact}</a>
          </nav>
        </div>
        <p className="disclaimer">{t.footer.disclaimer}</p>
        <p className="footer-rights">
          © {new Date().getFullYear()} {t.brand}. {t.footer.rights}.
        </p>
      </div>
    </footer>
  )
}
