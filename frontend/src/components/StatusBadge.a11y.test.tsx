import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { StatusBadge } from './StatusBadge'
import { ATTENDEE_STATUSES } from '@/types/status'
import { runAxe, criticalOrSerious } from '@/test/axe'

describe('StatusBadge a11y (fe-2.5 AC-1)', () => {
  it('ноль critical/serious нарушений axe для всех тонов', async () => {
    expect(ATTENDEE_STATUSES.length).toBeGreaterThan(0) // guard: цикл не вакуумный
    for (const status of ATTENDEE_STATUSES) {
      const { container, unmount } = render(<StatusBadge status={status} />)
      const violations = criticalOrSerious(await runAxe(container))
      expect(violations.map((v) => v.id)).toEqual([])
      unmount()
    }
  })
})
