import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DocumentUpload } from './DocumentUpload'

describe('DocumentUpload (Story 5.3)', () => {
  it('AC-1: метка «ФОТО ДОКУМЕНТА», accept включает PDF', () => {
    render(<DocumentUpload file={null} onFileChange={() => {}} />)
    expect(screen.getByText('ФОТО ДОКУМЕНТА')).toBeInTheDocument()
    const input = screen.getByLabelText(/ФОТО ДОКУМЕНТА/) as HTMLInputElement
    expect(input.accept).toContain('application/pdf')
  })

  it('AC-4: PDF → badge «PDF: имя» без <img>', () => {
    const pdf = new File([new Uint8Array([1, 2, 3])], 'doc.pdf', { type: 'application/pdf' })
    render(<DocumentUpload file={pdf} onFileChange={() => {}} />)
    expect(screen.getByText('PDF: doc.pdf')).toBeInTheDocument()
    expect(screen.queryByAltText(/Превью/)).not.toBeInTheDocument()
  })

  it('AC-2: изображение документа → preview <img>', () => {
    const img = new File([new Uint8Array([1, 2, 3])], 'scan.jpg', { type: 'image/jpeg' })
    render(<DocumentUpload file={img} onFileChange={() => {}} />)
    expect(screen.getByAltText(/Превью/)).toBeInTheDocument()
  })
})
