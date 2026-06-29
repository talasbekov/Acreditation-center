import { describe, it, expect, beforeEach } from 'vitest'
import i18n, { LANG_STORAGE_KEY } from '.'
import { HTML_LANG, syncHtmlLang } from './htmlLang'

describe('i18n bootstrap (Story fe-1.3)', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('ru')
  })

  it('AC-1: инициализирован, 5 namespaces, defaultNS common', () => {
    expect(i18n.isInitialized).toBe(true)
    for (const ns of ['common', 'validation', 'errors', 'status', 'nav']) {
      expect(i18n.options.ns).toContain(ns)
    }
    expect(i18n.options.defaultNS).toBe('common')
  })

  it('AC-1/AC-5d: все 5 namespaces резолвятся в ru', () => {
    expect(i18n.t('common:attendees.title')).toBe('Участники')
    expect(i18n.t('status:draft')).toBe('Черновик')
    expect(i18n.t('validation:search_min_chars')).toMatch(/3 символа/)
    expect(i18n.t('nav:language')).toBe('Язык интерфейса')
    expect(i18n.t('errors:blank')).toBe('Поле не может быть пустым.')
  })

  it('AC-4/AC-5e: errors namespace выведен из единого errors.json (анти-дрейф)', () => {
    expect(i18n.getResource('ru', 'errors', 'blank')).toBe('Поле не может быть пустым.')
  })

  it('AC-2: интерполяция params в common', () => {
    // dot вместо тире — устойчиво к типу дефиса (en-dash в каталоге)
    expect(i18n.t('common:pagination.showing', { from: 1, to: 50, total: 120 })).toMatch(
      /^Показано 1.50 из 120$/,
    )
  })

  it('AC-2: живой ре-рендер — en даёт другой текст', async () => {
    expect(i18n.t('common:attendees.title')).toBe('Участники')
    await i18n.changeLanguage('en')
    expect(i18n.t('common:attendees.title')).toBe('Attendees')
  })

  it('fe-1.4: kz-каталог заполнен → возвращает kk (не ru-фолбэк)', async () => {
    await i18n.changeLanguage('kz')
    expect(i18n.t('common:attendees.title')).toBe('Қатысушылар')
    expect(i18n.t('operatorForm:submit')).toBe('Сақтау')
  })

  it('AC-1: пустой namespace (errors kz) → фолбэк на ru', async () => {
    // errors kz пуст (errorsResource отбрасывает [ASSUMPTION]-плейсхолдеры) → фолбэк ru.
    await i18n.changeLanguage('kz')
    expect(i18n.t('errors:blank')).toBe('Поле не может быть пустым.')
  })

  it('AC-5a: ru — эффективный дефолт/фолбэк (неподдерживаемый язык → ru)', async () => {
    // setup форсит ru и маскирует чистую детекцию; здесь явно проверяем, что фолбэк-локаль
    // именно ru: неподдерживаемый код резолвится в ru-каталог.
    expect(i18n.options.fallbackLng).toBeTruthy()
    expect(JSON.stringify(i18n.options.fallbackLng)).toContain('ru')
    await i18n.changeLanguage('de') // нет в supportedLngs / без ресурсов
    expect(i18n.t('common:attendees.title')).toBe('Участники')
    await i18n.changeLanguage('ru')
  })

  it('AC-2/AC-5b: changeLanguage пишет выбор в localStorage', async () => {
    await i18n.changeLanguage('kz')
    expect(window.localStorage.getItem(LANG_STORAGE_KEY)).toBe('kz')
  })

  it('AC-3/AC-5c: <html lang> маппинг ru→ru, kz→kk, en→en', () => {
    expect(HTML_LANG).toEqual({ ru: 'ru', kz: 'kk', en: 'en' })
    syncHtmlLang('kz')
    expect(document.documentElement.lang).toBe('kk')
    syncHtmlLang('en')
    expect(document.documentElement.lang).toBe('en')
    syncHtmlLang('ru')
    expect(document.documentElement.lang).toBe('ru')
  })

  it('AC-3: смена языка синхронизирует <html lang> (kz→kk)', async () => {
    await i18n.changeLanguage('kz')
    expect(document.documentElement.lang).toBe('kk')
  })

  it('AC-4: детектор конвертит kk→kz, остальное не трогает', () => {
    const detection = i18n.options.detection as
      | { convertDetectedLanguage?: (l: string) => string }
      | undefined
    const conv = detection?.convertDetectedLanguage
    expect(typeof conv).toBe('function')
    expect(conv?.('kk-KZ')).toBe('kz')
    expect(conv?.('ru-RU')).toBe('ru-RU')
  })
})
