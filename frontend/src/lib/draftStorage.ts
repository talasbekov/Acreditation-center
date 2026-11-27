/** Старые версии сохраняли один черновик участника для всего профиля браузера. */
export function removeLegacyAttendeeDraft(): void {
  try {
    window.localStorage.removeItem('attendee_draft_v1')
  } catch {
    // Браузер может блокировать доступ к хранилищу. Форма работает в памяти.
  }
}
