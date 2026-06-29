import { useTranslation } from 'react-i18next'
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
  const { t } = useTranslation()
  return (
    <UploadZone
      id="photo"
      label={t('operatorForm:photo.label')}
      instruction={t('operatorForm:photo.instruction')}
      accept="image/jpeg,image/png"
      {...props}
    />
  )
}
