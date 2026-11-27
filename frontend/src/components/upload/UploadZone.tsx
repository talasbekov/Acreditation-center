import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

export interface UploadZoneProps {
  /** id input'а (совпадает с именем поля FormData: photo / docScan). */
  id: string
  /** Название зоны — оно же метка поля выбора файла. */
  label: string
  /** Форматы и лимиты — те же, что проверяет сервер (validators/photo.py). */
  instruction?: string
  /** Список MIME, напр. "image/jpeg,image/png" или "...,application/pdf". */
  accept: string
  file: File | null
  onFileChange: (file: File | null) => void
  error?: string
  /** P2-7: URL уже загруженного файла (edit) — превью, пока не выбран новый файл. */
  existingUrl?: string | null
}

const previewStyle = { minWidth: 150, minHeight: 200, maxHeight: 320, objectFit: 'contain' as const }

/**
 * Story 5.3 / этап D — зона загрузки с обязательным превью.
 * Изображение → превью через `URL.createObjectURL`. PDF браузер в `<img>` не рисует —
 * показываем имя файла; JPEG-превью приходит от сервера после сохранения.
 * Состояния: нет файла, текущий файл (правка), выбран новый файл, ошибка.
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

  // Превью только для изображений; objectURL обязательно освобождать.
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

  const hintId = instruction ? `${id}-hint` : ''
  const errorId = error ? `${id}-error` : ''

  return (
    <div className={`min-w-0 rounded-lg border-2 border-dashed p-4 ${error ? 'border-danger' : 'border-line'}`}>
      <label htmlFor={id} className="block text-base leading-6 font-semibold text-ink">
        {label}
      </label>
      {instruction && (
        <p id={hintId} className="mt-1 text-sm leading-5 text-ink-2">
          {instruction}
        </p>
      )}
      <input
        id={id}
        ref={inputRef}
        type="file"
        accept={accept}
        aria-describedby={[hintId, errorId].filter(Boolean).join(' ') || undefined}
        aria-invalid={error ? true : undefined}
        className="mt-3 block w-full max-w-full text-base text-ink file:mr-3 file:h-11 file:cursor-pointer file:rounded-md file:border file:border-field file:bg-surface file:px-4 file:font-semibold file:text-ink hover:file:bg-section"
        onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
      />
      {file && (
        <div className="mt-3">
          <p className="mb-2 text-sm leading-5 font-semibold text-success [overflow-wrap:anywhere]">
            {t('operatorForm:upload.selected', { name: file.name })}
          </p>
          {previewUrl ? (
            <img src={previewUrl} alt={t('operatorForm:upload.preview_alt', { label })} className="rounded border border-line" style={previewStyle} />
          ) : (
            <span className="inline-block rounded-md bg-info-bg px-2 py-1 text-sm text-info [overflow-wrap:anywhere]">
              {t('operatorForm:upload.pdf_badge', { name: file.name })}
            </span>
          )}
        </div>
      )}
      {/* P2-7: пока новый файл не выбран — показываем уже загруженное (edit). Сервер
          хранит docScan как JPEG (PDF конвертируется при сохранении) → всегда <img>. */}
      {!file && existingUrl && (
        <div className="mt-3">
          <p className="mb-1 text-sm leading-5 text-ink-2">{t('operatorForm:upload.current_note')}</p>
          <img src={existingUrl} alt={t('operatorForm:upload.current_alt', { label })} className="rounded border border-line" style={previewStyle} />
        </div>
      )}
      {error && (
        <p id={errorId} role="alert" className="mt-2 text-sm leading-5 font-semibold text-danger">
          {error}
        </p>
      )}
    </div>
  )
}
