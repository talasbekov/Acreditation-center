import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { ATTENDEE_STATUSES } from '@/types/status'

// fe-2.4 (review P1): РЕАЛЬНАЯ parity-проверка единого источника статусов.
// Фронтовый ATTENDEE_STATUSES (types/status.ts) должен совпадать с backend
// `eventproject/state_machine.py` (источник правды). Ловит дрейф: добавили/переименовали
// статус на бэке (напр. будущий return-flow `rejected`) → тест падает, а не молча
// деградирует (бейдж→neutral + сырой код в RU, фильтр теряет опцию). Живёт в scripts/
// (node:fs, вне app-typecheck; в vite.config test.include). cwd vitest = frontend/.
const py = readFileSync(resolve(process.cwd(), '../eventproject/state_machine.py'), 'utf8')

function backendStatuses(): string[] {
  // Извлекаем строковые значения из `class AttendeeStatus:` (`NAME = "value"`), в порядке объявления.
  const body = py.match(/class AttendeeStatus:([\s\S]*?)\n\n/)
  if (!body) throw new Error('class AttendeeStatus не найден в state_machine.py')
  return [...body[1].matchAll(/=\s*"(\w+)"/g)].map((m) => m[1])
}

describe('ATTENDEE_STATUSES parity (fe-2.4 — frontend ↔ backend state_machine.py)', () => {
  it('фронтовый набор статусов === backend (тот же порядок переходов)', () => {
    expect([...ATTENDEE_STATUSES]).toEqual(backendStatuses())
  })
})
