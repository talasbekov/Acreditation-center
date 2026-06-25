import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PhotoUpload } from './PhotoUpload'

describe('PhotoUpload (Story 5.3)', () => {
  it('AC-1: крупная метка «ФОТО УЧАСТНИКА (3×4)» + инструкция', () => {
    render(<PhotoUpload file={null} onFileChange={() => {}} />)
    expect(screen.getByText('ФОТО УЧАСТНИКА (3×4)')).toBeInTheDocument()
    expect(screen.getByText('Анфас, светлый фон, без очков')).toBeInTheDocument()
    const input = screen.getByLabelText(/ФОТО УЧАСТНИКА/) as HTMLInputElement
    expect(input.accept).toBe('image/jpeg,image/png')
  })

  it('AC-2: выбор изображения → onFileChange и preview <img>', () => {
    const onFileChange = vi.fn()
    const { rerender } = render(<PhotoUpload file={null} onFileChange={onFileChange} />)
    const file = new File([new Uint8Array([1, 2, 3])], 'p.jpg', { type: 'image/jpeg' })
    fireEvent.change(screen.getByLabelText(/ФОТО УЧАСТНИКА/), { target: { files: [file] } })
    expect(onFileChange).toHaveBeenCalledWith(file)
    rerender(<PhotoUpload file={file} onFileChange={onFileChange} />)
    expect(screen.getByAltText(/Превью/)).toBeInTheDocument()
  })

  it('показывает ошибку под зоной (role=alert)', () => {
    render(
      <PhotoUpload
        file={null}
        onFileChange={() => {}}
        error="Файл слишком большой (максимум 5 МБ)"
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Файл слишком большой')
  })
})
