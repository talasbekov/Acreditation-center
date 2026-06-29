import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

export interface UploadZoneProps {
  /** id input'а (совпадает с именем поля FormData: photo / docScan). */
  id: string
  /** Крупная высококонтрастная метка (AC-1: ≥18px bold). */
  label: string
  /** Инструкция под меткой. */
  instruction?: string
  /** Список MIME, напр. "image/jpeg,image/png" или "...,application/pdf". */
  accept: string
  file: File | null
  onFileChange: (file: File | null) => void
  error?: string
  /** P2-7: URL уже загруженного файла (edit) — превью, пока не выбран новый файл. */
  existingUrl?: string | null
}

/**
 * Story 5.3 — переиспользуемая зона загрузки с обязательным preview (AC-2).
 * Изображение → preview через `URL.createObjectURL` (≥150×200px). PDF (документ)
 * браузер не рисует в `<img>` — показываем badge «PDF: <имя>»; JPEG-preview
 * приходит от сервера после сохранения (AC-4). Метка крупная/контрастная (AC-1).
 */
export function UploadZone({
  id,
  label,
  instruction,
  accept,
  file,
  onFileChange,
  error,
  existingUrl,
}: UploadZoneProps) {
  const { t } = useTranslation()
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Preview только для изображений; cleanup objectURL — обязателен (утечка иначе).
  useEffect(() => {
    if (file && file.type.startsWith('image/')) {
      const url = URL.createObjectURL(file)
      setPreviewUrl(url)
      return () => URL.revokeObjectURL(url)
    }
    setPreviewUrl(null)
    return undefined
  }, [file])

  // Сброс формы (reset → file=null) должен очищать и нативный input.
  useEffect(() => {
    if (!file && inputRef.current) inputRef.current.value = ''
  }, [file])

  return (
    <div className="rounded-md border border-input-border p-4">
      <label htmlFor={id} className="block">
        <span className="mb-1 block text-lg font-bold text-text">{label}</span>
        {instruction && (
          <span className="mb-2 block text-sm text-text">{instruction}</span>
        )}
      </label>
      <input
        id={id}
        ref={inputRef}
        type="file"
        accept={accept}
        // fe-2.7 (AC-3): причина Pillow-отказа связана с зоной для SR — aria-describedby
        // указывает на текст ошибки, aria-invalid помечает контрол невалидным.
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className="block w-full text-base"
        onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
      />
      {file && (
        <div className="mt-3">
          {previewUrl ? (
            <img
              src={previewUrl}
              alt={t('operatorForm:upload.preview_alt', { label })}
              className="rounded border border-input-border"
              style={{ minWidth: 150, minHeight: 200, maxHeight: 320, objectFit: 'contain' }}
            />
          ) : (
            <span className="inline-block rounded bg-surface-muted px-2 py-1 text-sm">
              {t('operatorForm:upload.pdf_badge', { name: file.name })}
            </span>
          )}
        </div>
      )}
      {/* P2-7: пока новый файл не выбран — показываем уже загруженное (edit). Сервер
          хранит docScan как JPEG (PDF конвертируется при сохранении) → всегда <img>. */}
      {!file && existingUrl && (
        <div className="mt-3">
          <p className="mb-1 text-sm text-text-muted">{t('operatorForm:upload.current_label')}</p>
          <img
            src={existingUrl}
            alt={t('operatorForm:upload.current_alt', { label })}
            className="rounded border border-input-border"
            style={{ minWidth: 150, minHeight: 200, maxHeight: 320, objectFit: 'contain' }}
          />
        </div>
      )}
      {error && (
        <p id={`${id}-error`} role="alert" className="mt-1 text-sm text-status-rejected">
          {error}
        </p>
      )}
    </div>
  )
}
