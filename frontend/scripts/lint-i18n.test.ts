import { describe, it, expect } from 'vitest'
import { findViolations } from './lint-i18n.mjs'

// Story fe-1.4 (AC-1): доказываем, что i18n-lint реально ловит кириллические литералы
// и не флагует легитимные случаи (t()-ключи, whitelist, комментарии).
describe('i18n-lint findViolations (Story fe-1.4)', () => {
  it('ловит кириллический строковый литерал (одинарные кавычки)', () => {
    const v = findViolations('src/components/Foo.tsx', "const x = 'Сохранить'")
    expect(v.some((p) => p.rule === 'no-cyrillic-literal' && p.text === "'Сохранить'")).toBe(true)
  })

  it('ловит литерал в двойных кавычках (JSX-атрибут)', () => {
    const v = findViolations('a.tsx', '<input placeholder="Поиск по имени" />')
    expect(v.length).toBeGreaterThan(0)
  })

  it('ловит литерал в шаблонной строке (backtick)', () => {
    const v = findViolations('a.tsx', 'const a = `Превью`')
    expect(v.some((p) => p.rule === 'no-cyrillic-literal')).toBe(true)
  })

  it('НЕ флагует ASCII i18n-ключ t(...) (после извлечения)', () => {
    expect(findViolations('a.tsx', "t('operatorForm:label.surname')")).toEqual([])
  })

  it('НЕ флагует кириллицу в line-комментарии', () => {
    expect(findViolations('a.tsx', "// Сохранить черновик\nconst x = 1")).toEqual([])
  })

  it('НЕ флагует кириллицу в block-комментарии', () => {
    expect(findViolations('a.tsx', '/* Найден черновик */ const x = 1')).toEqual([])
  })

  it('whitelist: чистый токен ИИН/ФИО допускается', () => {
    expect(findViolations('a.tsx', "const a = 'ИИН'")).toEqual([])
    expect(findViolations('a.tsx', "const a = 'ФИО'")).toEqual([])
  })

  it('whitelist НЕ спасает, если есть прочая кириллица помимо токена', () => {
    const v = findViolations('a.tsx', "const a = 'Поиск по ФИО'")
    expect(v.some((p) => p.rule === 'no-cyrillic-literal')).toBe(true)
  })

  it('НЕ флагует чисто латинский/числовой литерал', () => {
    expect(findViolations('a.tsx', "const a = 'image/jpeg,image/png'")).toEqual([])
    expect(findViolations('a.tsx', "const a = 'PDF'")).toEqual([])
  })

  it('сообщает корректные line/col', () => {
    const v = findViolations('a.tsx', "const x = 1\nconst y = 'Имя'")
    expect(v[0]).toMatchObject({ line: 2, rule: 'no-cyrillic-literal' })
  })

  // review fe-1.4: голый JSX-текст (не кавычки) — самый частый React-вектор.
  it('ловит голый JSX-текст (`<th>Статус</th>`)', () => {
    const v = findViolations('a.tsx', '<th>Статус</th>')
    expect(v.some((p) => p.rule === 'no-cyrillic-jsx-text')).toBe(true)
  })

  it('НЕ флагует JSX-выражение `>{t(...)}<` (извлечённый текст)', () => {
    expect(findViolations('a.tsx', "<th>{t('common:table.status')}</th>")).toEqual([])
  })

  // review fe-1.4: charclass покрывает казахские глифы (ә/қ/ң/…), не только русские.
  it('ловит литерал из казах-специфичных букв (ә/қ/ң)', () => {
    const v = findViolations('a.tsx', "const a = 'Тегіңізді көрсетіңіз'")
    expect(v.some((p) => p.rule === 'no-cyrillic-literal')).toBe(true)
  })
})
