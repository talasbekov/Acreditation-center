import '@testing-library/jest-dom'

// jsdom не реализует URL.createObjectURL/revokeObjectURL — нужны для preview (Story 5.3).
if (typeof URL.createObjectURL !== 'function') {
  URL.createObjectURL = () => 'blob:mock-preview'
  URL.revokeObjectURL = () => {}
}
