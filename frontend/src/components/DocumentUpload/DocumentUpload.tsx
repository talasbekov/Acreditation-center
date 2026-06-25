import { UploadZone } from '@/components/upload/UploadZone'

export interface DocumentUploadProps {
  file: File | null
  onFileChange: (file: File | null) => void
  error?: string
  /** P2-7: URL уже загруженного документа (edit; сервер хранит JPEG). */
  existingUrl?: string | null
}

/**
 * Story 5.3 — зона «ФОТО ДОКУМЕНТА». Физически отдельная от фото участника.
 * Принимает изображение ИЛИ PDF (сервер конвертирует PDF→JPEG, затем та же
 * 3×4-валидация, что и у фото — решение Erda 2026-06-24).
 */
export function DocumentUpload(props: DocumentUploadProps) {
  return (
    <UploadZone
      id="docScan"
      label="ФОТО ДОКУМЕНТА"
      instruction="Вертикально, формат 3×4 (можно PDF)"
      accept="image/jpeg,image/png,application/pdf"
      {...props}
    />
  )
}
