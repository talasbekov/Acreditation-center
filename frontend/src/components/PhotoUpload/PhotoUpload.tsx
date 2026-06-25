import { UploadZone } from '@/components/upload/UploadZone'

export interface PhotoUploadProps {
  file: File | null
  onFileChange: (file: File | null) => void
  error?: string
  /** P2-7: URL уже загруженного фото (edit). */
  existingUrl?: string | null
}

/**
 * Story 5.3 — зона «ФОТО УЧАСТНИКА (3×4)». Физически отдельная от документа.
 * Принимает только изображения; серверная Pillow-валидация (3×4, ≥600×800, ≤5МБ).
 */
export function PhotoUpload(props: PhotoUploadProps) {
  return (
    <UploadZone
      id="photo"
      label="ФОТО УЧАСТНИКА (3×4)"
      instruction="Анфас, светлый фон, без очков"
      accept="image/jpeg,image/png"
      {...props}
    />
  )
}
