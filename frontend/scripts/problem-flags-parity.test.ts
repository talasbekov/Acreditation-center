import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { PROBLEM_FLAGS } from '@/types/problemFlags'

// fe-3.1 (AC-2): РЕАЛЬНАЯ parity-проверка закрытого набора проблемных флагов.
// Фронтовый PROBLEM_FLAGS (types/problemFlags.ts) обязан совпадать с backend
// `eventproject/problem_flags.py` (источник правды). Ловит дрейф: добавили/переименовали
// флаг на бэке → тест падает, а не молча роняет фильтр/представление. Живёт в scripts/
// (node:fs, вне app-typecheck; в vite.config test.include). cwd vitest = frontend/.
const py = readFileSync(resolve(process.cwd(), '../eventproject/problem_flags.py'), 'utf8')

function backendFlags(): string[] {
  // Порядок задаёт КОРТЕЖ `PROBLEM_FLAGS` (его читают compute/filter/export), а не
  // объявление class — реордер кортежа без class иначе остался бы незаметен. Резолвим
  // ссылки `ProblemFlag.NAME` кортежа через карту NAME→value из class.
  const cls = py.match(/class ProblemFlag:([\s\S]*?)\n\n/)
  if (!cls) throw new Error('class ProblemFlag не найден в problem_flags.py')
  const valueByName = new Map<string, string>(
    [...cls[1].matchAll(/(\w+)\s*=\s*"(\w+)"/g)].map((m) => [m[1], m[2]]),
  )
  const tuple = py.match(/PROBLEM_FLAGS\s*=\s*\(([\s\S]*?)\)/)
  if (!tuple) throw new Error('кортеж PROBLEM_FLAGS не найден в problem_flags.py')
  return [...tuple[1].matchAll(/ProblemFlag\.(\w+)/g)].map((m) => {
    const value = valueByName.get(m[1])
    if (value === undefined) throw new Error(`ProblemFlag.${m[1]} нет в class ProblemFlag`)
    return value
  })
}

describe('PROBLEM_FLAGS parity (fe-3.1 — frontend ↔ backend problem_flags.py)', () => {
  it('фронтовый закрытый набор флагов === backend (тот же порядок)', () => {
    expect([...PROBLEM_FLAGS]).toEqual(backendFlags())
  })
})
