import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { useState } from 'react'
import { ReturnReasonDialog } from './ReturnReasonDialog'

/** Харнес с триггером — для проверки возврата фокуса на кнопку, открывшую модалку. */
function Harness({ onSubmit = vi.fn() }: { onSubmit?: (r: string) => void }) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button data-testid="trigger" onClick={() => setOpen(true)}>
        открыть
      </button>
      <ReturnReasonDialog open={open} onClose={() => setOpen(false)} onSubmit={onSubmit} />
    </div>
  )
}

describe('ReturnReasonDialog (fe-3.5 AC-3)', () => {
  it('закрыт → ничего не рендерит', () => {
    render(<ReturnReasonDialog open={false} onClose={() => {}} onSubmit={() => {}} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('открыт → role=dialog + aria-modal; фокус на поле причины', () => {
    render(<Harness />)
    fireEvent.click(screen.getByTestId('trigger'))
    expect(screen.getByRole('dialog')).toHaveAttribute('aria-modal', 'true')
    expect(document.activeElement).toBe(screen.getByLabelText('Причина возврата'))
  })

  it('submit disabled пока причина пуста/только пробелы; активна с текстом', () => {
    render(<Harness />)
    fireEvent.click(screen.getByTestId('trigger'))
    const submit = screen.getByRole('button', { name: 'Подтвердить возврат' })
    const reason = screen.getByLabelText('Причина возврата')
    expect(submit).toBeDisabled()
    fireEvent.change(reason, { target: { value: '   ' } })
    expect(submit).toBeDisabled()
    fireEvent.change(reason, { target: { value: 'Нет фото' } })
    expect(submit).toBeEnabled()
  })

  it('submit → onSubmit с trimmed-причиной', () => {
    const onSubmit = vi.fn()
    render(<Harness onSubmit={onSubmit} />)
    fireEvent.click(screen.getByTestId('trigger'))
    fireEvent.change(screen.getByLabelText('Причина возврата'), {
      target: { value: '  Нет фото  ' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить возврат' }))
    expect(onSubmit).toHaveBeenCalledWith('Нет фото')
  })

  it('Esc → закрытие + возврат фокуса на триггер (не в body)', () => {
    render(<Harness />)
    const trigger = screen.getByTestId('trigger')
    trigger.focus() // jsdom: click не фокусирует — фокусируем явно (как браузер)
    fireEvent.click(trigger)
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(document.activeElement).toBe(trigger)
  })

  it('«Отмена» → закрытие без onSubmit', () => {
    const onSubmit = vi.fn()
    render(<Harness onSubmit={onSubmit} />)
    fireEvent.click(screen.getByTestId('trigger'))
    fireEvent.click(screen.getByRole('button', { name: 'Отмена' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
