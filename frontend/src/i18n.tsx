import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { ru, type Dictionary } from './locales/ru'
import { kk } from './locales/kk'

export type Lang = 'ru' | 'kk'

const dictionaries: Record<Lang, Dictionary> = { ru, kk }
const STORAGE_KEY = 'smartprotocol.lang'

type I18nValue = {
  lang: Lang
  t: Dictionary
  setLang: (lang: Lang) => void
}

const I18nContext = createContext<I18nValue | null>(null)

function readInitialLang(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'ru' || stored === 'kk') return stored
  } catch {
    // приватный режим или заблокированное хранилище — не повод падать
  }
  return navigator.language?.toLowerCase().startsWith('kk') ? 'kk' : 'ru'
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(readInitialLang)

  useEffect(() => {
    document.documentElement.lang = lang
    try {
      localStorage.setItem(STORAGE_KEY, lang)
    } catch {
      // не критично: язык просто не запомнится между визитами
    }
  }, [lang])

  const value = useMemo(() => ({ lang, t: dictionaries[lang], setLang }), [lang])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext)
  if (!value) throw new Error('useI18n должен вызываться внутри I18nProvider')
  return value
}

/** Подстановка вида {name} — форматирования на весь ICU здесь не нужно. */
export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key) =>
    key in values ? String(values[key]) : match,
  )
}
