import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import i18n from '@/i18n'
import { LanguageSwitcher } from './LanguageSwitcher'

describe('LanguageSwitcher (Story fe-1.3)', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('ru')
  })

  it('AC-2: показывает ru/kz/en; активный язык disabled', () => {
    render(<LanguageSwitcher />)
    expect(screen.getByRole('button', { name: 'RU' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'KZ' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'EN' })).toBeEnabled()
  })

  it('AC-2: клик EN переключает язык на en', async () => {
    render(<LanguageSwitcher />)
    fireEvent.click(screen.getByRole('button', { name: 'EN' }))
    await waitFor(() => expect(i18n.resolvedLanguage).toBe('en'))
  })

  it('AC-3: клик KZ синхронизирует <html lang>=kk', async () => {
    render(<LanguageSwitcher />)
    fireEvent.click(screen.getByRole('button', { name: 'KZ' }))
    await waitFor(() => expect(document.documentElement.lang).toBe('kk'))
  })

  it('AC-2: выбор KZ помечает KZ активным (active=language, не resolvedLanguage)', async () => {
    // Регрессия: при active=resolvedLanguage пустые kz-каталоги увели бы active на ru,
    // и KZ никогда не подсветился бы. active=i18n.language это исключает.
    render(<LanguageSwitcher />)
    fireEvent.click(screen.getByRole('button', { name: 'KZ' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'KZ' })).toBeDisabled())
    expect(i18n.language).toBe('kz')
    expect(screen.getByRole('button', { name: 'RU' })).toBeEnabled()
  })
})
