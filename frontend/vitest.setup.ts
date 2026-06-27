import '@testing-library/jest-dom'
import i18n from './src/i18n'

// jsdom не реализует URL.createObjectURL/revokeObjectURL — нужны для preview (Story 5.3).
if (typeof URL.createObjectURL !== 'function') {
  URL.createObjectURL = () => 'blob:mock-preview'
  URL.revokeObjectURL = () => {}
}

// fe-1.3: детерминизм тестов — фиксируем ru. Иначе language-detector берёт
// navigator.language jsdom ('en-US') → дефолт уехал бы на en, и getByText('Участники')
// / 'Вперёд' в существующих тестах упали бы. Ресурсы бандлятся → применяется синхронно.
void i18n.changeLanguage('ru')
