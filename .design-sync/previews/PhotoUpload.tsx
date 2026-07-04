import { PhotoUpload } from 'frontend'

// Зона «ФОТО УЧАСТНИКА (3×4)» (Story 5.3): только изображения, метка/инструкция из i18n.
// Файлы не конструируем — заполненное состояние через existingUrl, отказ — через error.
const portrait =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="400"><rect width="300" height="400" fill="#e3e5e8"/><circle cx="150" cy="150" r="60" fill="#7c828a"/><path d="M60 400c0-70 40-110 90-110s90 40 90 110" fill="#7c828a"/></svg>',
  )

// Пустое состояние: метка ФОТО УЧАСТНИКА (3×4) + инструкция, preview ещё нет.
export function Empty() {
  return (
    <div style={{ maxWidth: 380 }}>
      <PhotoUpload file={null} onFileChange={() => {}} />
    </div>
  )
}

// Редактирование заявки: показываем уже загруженное фото 3×4.
export function WithExisting() {
  return (
    <div style={{ maxWidth: 380 }}>
      <PhotoUpload file={null} onFileChange={() => {}} existingUrl={portrait} />
    </div>
  )
}

// Серверная Pillow-валидация отклонила фото (не 3×4 / мало пикселей / >5 МБ).
export function WithError() {
  return (
    <div style={{ maxWidth: 380 }}>
      <PhotoUpload
        file={null}
        onFileChange={() => {}}
        error="Фото должно быть 3×4 (мин. 600×800), файл до 5 МБ"
      />
    </div>
  )
}
