// Этап D: рабочий контекст реестра на время сессии вкладки.
//
// Статус и страница живут в адресе (`?status=ready&page=2`) — без персональных данных,
// переживают перезагрузку и кнопку «Назад». Строка поиска — это ФИО, поэтому её нет ни
// в адресе, ни в localStorage/sessionStorage: только в памяти страницы. Перезагрузка или
// закрытие вкладки её стирает, поэтому на общем компьютере поиск не достаётся следующему.

interface RegistryState {
  search: string
  /** Адрес реестра с фильтрами — куда возвращает «К списку участников». */
  listUrl: string
  /** Участник, карточку которого открыли последним: при возврате фокус на его строке. */
  lastOpenedId: number | null
}

const initial = (): RegistryState => ({ search: '', listUrl: '/', lastOpenedId: null })

let state: RegistryState = initial()

export const registryState = {
  get: (): Readonly<RegistryState> => state,
  set(patch: Partial<RegistryState>) {
    state = { ...state, ...patch }
  },
  /** Сбросить (смена пользователя, тесты). */
  reset() {
    state = initial()
  },
}
