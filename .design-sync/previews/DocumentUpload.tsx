import { DocumentUpload } from 'frontend'

// Зона «ФОТО ДОКУМЕНТА» (Story 5.3): изображение ИЛИ PDF; сервер конвертирует PDF→JPEG
// и хранит его, поэтому в edit всегда <img>. Файлы не конструируем — existingUrl/error.
const docScan =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="400">' +
      '<rect width="300" height="400" fill="#eceef0"/>' +
      '<rect x="30" y="30" width="240" height="150" rx="8" fill="#d3d7db"/>' +
      '<rect x="48" y="60" width="70" height="90" fill="#9aa0a6"/>' +
      '<rect x="135" y="66" width="110" height="12" rx="6" fill="#9aa0a6"/>' +
      '<rect x="135" y="92" width="90" height="12" rx="6" fill="#9aa0a6"/>' +
      '<rect x="135" y="118" width="100" height="12" rx="6" fill="#9aa0a6"/>' +
      '<rect x="30" y="210" width="240" height="10" rx="5" fill="#c3c8cd"/>' +
      '<rect x="30" y="236" width="200" height="10" rx="5" fill="#c3c8cd"/>' +
      '<rect x="30" y="262" width="220" height="10" rx="5" fill="#c3c8cd"/>' +
      '</svg>',
  )

// Пустое состояние: метка ФОТО ДОКУМЕНТА + инструкция «можно PDF».
export function Empty() {
  return (
    <div style={{ maxWidth: 380 }}>
      <DocumentUpload file={null} onFileChange={() => {}} />
    </div>
  )
}

// Редактирование: документ уже загружен, сервер отдал JPEG-превью.
export function WithExisting() {
  return (
    <div style={{ maxWidth: 380 }}>
      <DocumentUpload file={null} onFileChange={() => {}} existingUrl={docScan} />
    </div>
  )
}

// Отказ обработки: не удалось привести документ к 3×4 или PDF слишком большой.
export function WithError() {
  return (
    <div style={{ maxWidth: 380 }}>
      <DocumentUpload
        file={null}
        onFileChange={() => {}}
        error="Не удалось обработать документ: нужен формат 3×4 (мин. 600×800) или PDF до 5 МБ"
      />
    </div>
  )
}
