import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { useTranslation } from 'react-i18next'
import i18n from '@/i18n'
import type { ProblemDetail } from '@/api/client'
import { mapApiError } from './mapApiError'
import codesJson from './errors.codes.json'

// AC-3: коды читаем из реестра (единый источник), не хардкодим — иначе тест тавтологичен.
const REGISTRY_CODES = Object.keys(codesJson)

// Смонтированный компонент ошибки (AC-3: оракул — getByText, не функция напрямую).
function ErrorProbe({ problem }: { problem: ProblemDetail | undefined }) {
  const { t, i18n: inst } = useTranslation()
  return <p data-testid="err">{mapApiError(problem, t, inst)}</p>
}

describe('mapApiError (Story fe-1.2)', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('ru')
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('реестр непустой (sanity: перебор не вырожден)', () => {
    expect(REGISTRY_CODES.length).toBeGreaterThan(0)
  })

  // AC-3: КАЖДЫЙ код реестра рендерит непустой ru-текст ≠ ключу ≠ fallback (кроме unknown),
  // БЕЗ утечки `{{var}}` — params строим из сигнатуры реестра (заодно проверяем, что все
  // плейсхолдеры шаблона покрыты сигнатурой errors.codes.json).
  const codesSig = codesJson as Record<string, { params: string[] }>
  it.each(REGISTRY_CODES)('AC-3: код %s → непустой текст ≠ ключ ≠ fallback, без {{leak}}', (code) => {
    const unknownText = i18n.t('errors:unknown')
    const sig = codesSig[code]?.params ?? []
    const params = Object.fromEntries(sig.map((name) => [name, 'X']))
    render(<ErrorProbe problem={{ type: code, params }} />)
    const text = screen.getByTestId('err').textContent ?? ''
    expect(text.length).toBeGreaterThan(0)
    expect(text).not.toContain('{{') // все {{var}} покрыты сигнатурой реестра
    expect(text).not.toBe(`errors:${code}`)
    if (code !== 'unknown') {
      expect(text).not.toBe(unknownText)
    } else {
      expect(text).toBe(unknownText) // unknown и ЕСТЬ fallback
    }
  })

  it('AC-1: известный код с params интерполируется', () => {
    render(
      <ErrorProbe
        problem={{
          type: 'iin_dob_mismatch',
          field: 'iin',
          params: { iin_dob: '05.12.1985', entered_dob: '12.05.1985' },
        }}
      />,
    )
    const text = screen.getByTestId('err').textContent ?? ''
    expect(text).toContain('05.12.1985')
    expect(text).toContain('12.05.1985')
    expect(text).not.toContain('{{') // плейсхолдер не утёк
  })

  it('AC-2: неизвестный код → fallback errors:unknown, лог type, сырой код НЕ в DOM', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    render(<ErrorProbe problem={{ type: 'totally_unregistered_code_xyz', params: {} }} />)
    const text = screen.getByTestId('err').textContent ?? ''
    expect(text).toBe(i18n.t('errors:unknown'))
    expect(text.length).toBeGreaterThan(0)
    expect(text).not.toContain('totally_unregistered_code_xyz') // сырой код не показан
    expect(warn).toHaveBeenCalledWith('[error-mapper] неизвестный код ошибки:', 'totally_unregistered_code_xyz')
  })

  it('AC-2: problem=undefined → fallback без лога', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    render(<ErrorProbe problem={undefined} />)
    expect(screen.getByTestId('err').textContent).toBe(i18n.t('errors:unknown'))
    expect(warn).not.toHaveBeenCalled()
  })
})
