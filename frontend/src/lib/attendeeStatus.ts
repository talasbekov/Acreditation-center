// Подписи статусов участника — те же, что на HTML-страницах оператора
// (eventproject/templatetags/lifecycle_tags.py, RU).

export const STATUS_LABELS: Record<string, string> = {
  draft: 'Черновик',
  submitted: 'Отправлен на проверку',
  in_review: 'На проверке',
  ready: 'Допущен',
  exported: 'Допущен, передан в службу',
}

export const RETURNED_LABEL = 'Возвращён на доработку'

/** Подпись статуса; черновик с причиной возврата — «Возвращён на доработку». */
export function statusLabel(status: string, returned = false): string {
  if (status === 'draft' && returned) return RETURNED_LABEL
  return STATUS_LABELS[status] ?? status
}

/** Оператор правит и отправляет только черновик (сервер отвечает так же). */
export function isOperatorEditable(status: string): boolean {
  return status === 'draft'
}
