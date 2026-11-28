// Статусы участника — те же, что на HTML-страницах оператора
// (eventproject/templatetags/lifecycle_tags.py). Подписи — каталог `status` (ru/kz/en).

/** Коды статусов в порядке жизненного цикла (services/lifecycle.py). */
export const STATUS_CODES = ['draft', 'submitted', 'in_review', 'ready', 'exported'] as const

export function isStatusCode(value: string): boolean {
  return (STATUS_CODES as readonly string[]).includes(value)
}

/** Ключ подписи статуса; черновик, возвращённый проверяющим, — `status:returned`. */
export function statusKey(status: string, returned = false): string {
  if (status === 'draft' && returned) return 'status:returned'
  return `status:${status}`
}

/** Оператор правит и отправляет только черновик (сервер отвечает так же). */
export function isOperatorEditable(status: string): boolean {
  return status === 'draft'
}
