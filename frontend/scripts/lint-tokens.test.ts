import { describe, it, expect } from 'vitest'
import { findViolations } from './lint-tokens.mjs'

// Story fe-2.1 (AC-3): доказываем, что токен-lint реально ловит нарушения (не тавтология).
describe('token-lint findViolations (Story fe-2.1)', () => {
  it('ловит сырой hex в .tsx', () => {
    const v = findViolations('src/components/Foo.tsx', 'const c = "#fff"')
    expect(v.some((x) => x.rule === 'no-raw-hex' && x.text === '#fff')).toBe(true)
  })

  it('ловит сырой hex в .css (не index.css)', () => {
    const v = findViolations('src/other.css', '.x { color: #1b1f24; }')
    expect(v.some((x) => x.rule === 'no-raw-hex')).toBe(true)
  })

  it('ловит light-only классы bg-white / bg-black / text-black в .tsx', () => {
    expect(findViolations('a.tsx', '<div className="bg-white" />').length).toBeGreaterThan(0)
    expect(findViolations('a.tsx', 'bg-black').length).toBeGreaterThan(0)
    expect(findViolations('a.tsx', 'text-black').length).toBeGreaterThan(0)
  })

  it('РАЗРЕШАЕТ hex в src/index.css (токен-блок)', () => {
    expect(findViolations('src/index.css', '  --canvas: #f4f5f6;')).toEqual([])
  })

  it('пропускает токен-утилиты в чистом компоненте', () => {
    const v = findViolations(
      'src/components/ui/button.tsx',
      "default: 'bg-primary text-primary-foreground hover:bg-primary-hover rounded-md'",
    )
    expect(v).toEqual([])
  })

  it('не флагует #react-root (после # нет hex-цифр)', () => {
    expect(findViolations('src/other.css', '#react-root { color: red; }')).toEqual([])
  })

  it('не флагует text-white (валиден на primary; вне запрещённого набора)', () => {
    expect(findViolations('a.tsx', 'text-white').length).toBe(0)
  })

  // code-review fe-2.1 patches:
  it('не флагует hex в line-комментарии (.tsx)', () => {
    expect(findViolations('a.tsx', '// old color was #f4f5f6').length).toBe(0)
  })

  it('не флагует hex в block-комментарии (.tsx / .css)', () => {
    expect(findViolations('a.tsx', '/* token #1b1f24 */ const x = 1').length).toBe(0)
    expect(findViolations('src/other.css', '/* было #fff */ .x{}').length).toBe(0)
  })

  it('ВСЁ ЕЩЁ ловит hex в строке-литерале (не комментарий)', () => {
    expect(findViolations('a.tsx', "const c = '#fff'").some((x) => x.rule === 'no-raw-hex')).toBe(true)
  })

  it('не флагует dark:bg-white (легитимный dark-utility)', () => {
    expect(findViolations('a.tsx', 'className="dark:bg-white"').length).toBe(0)
  })

  it('флагует hover:bg-white (всё ещё light-only)', () => {
    expect(findViolations('a.tsx', 'hover:bg-white').some((x) => x.rule === 'no-light-only-class')).toBe(true)
  })

  it('exempt заякорен: вложенный …/src/index.css НЕ освобождён', () => {
    expect(findViolations('src/vendor/src/index.css', 'color: #fff;').length).toBeGreaterThan(0)
  })

  it('сканирует .jsx (hex ловится)', () => {
    expect(findViolations('src/Foo.jsx', "style={{color:'#000'}}").some((x) => x.rule === 'no-raw-hex')).toBe(true)
  })
})
