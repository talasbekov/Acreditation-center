import { UploadZone } from 'frontend'

// Переиспользуемая зона загрузки (Story 5.3): крупная контрастная метка, инструкция,
// нативный file-input, обязательный preview. Файлы не конструируем (fake-байты →
// битая картинка) — заполненное состояние показываем через existingUrl, ошибку — error.
const portrait =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="400"><rect width="300" height="400" fill="#e3e5e8"/><circle cx="150" cy="150" r="60" fill="#7c828a"/><path d="M60 400c0-70 40-110 90-110s90 40 90 110" fill="#7c828a"/></svg>',
  )

// Пустое состояние: метка + инструкция + input, preview ещё нет.
export function Empty() {
  return (
    <div style={{ maxWidth: 380 }}>
      <UploadZone
        id="photo"
        label="ФОТО УЧАСТНИКА (3×4)"
        instruction="Анфас, светлый фон, без очков"
        accept="image/jpeg,image/png"
        file={null}
        onFileChange={() => {}}
      />
    </div>
  )
}

// Режим редактирования: файл ещё не выбран, показываем уже загруженное изображение.
export function WithExisting() {
  return (
    <div style={{ maxWidth: 380 }}>
      <UploadZone
        id="photo"
        label="ФОТО УЧАСТНИКА (3×4)"
        instruction="Анфас, светлый фон, без очков"
        accept="image/jpeg,image/png"
        file={null}
        onFileChange={() => {}}
        existingUrl={portrait}
      />
    </div>
  )
}

// Отказ серверной Pillow-валидации: aria-invalid + role="alert" красным.
export function WithError() {
  return (
    <div style={{ maxWidth: 380 }}>
      <UploadZone
        id="photo"
        label="ФОТО УЧАСТНИКА (3×4)"
        instruction="Анфас, светлый фон, без очков"
        accept="image/jpeg,image/png"
        file={null}
        onFileChange={() => {}}
        error="Фото должно быть 3×4 (мин. 600×800), файл до 5 МБ"
      />
    </div>
  )
}
