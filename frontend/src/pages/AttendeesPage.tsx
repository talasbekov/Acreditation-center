import { useQuery } from '@tanstack/react-query'
import { getAttendees } from '@/api/attendees'
import { Button } from '@/components/ui/button'

/** Smoke-страница bootstrap: подтверждает authed-вызов /api/v1/attendees/ (AC-3). */
export function AttendeesPage() {
  const { data, isPending, error, refetch } = useQuery({
    queryKey: ['attendees', 1],
    queryFn: () => getAttendees({ page: 1 }),
  })

  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="mb-4 text-2xl font-semibold text-neutral-900">Участники</h1>
      <p className="mb-4 text-base text-neutral-700">
        {isPending && 'Загрузка…'}
        {error && 'Не удалось загрузить список.'}
        {data && `Всего участников: ${data.count}`}
      </p>
      <Button onClick={() => void refetch()}>Обновить</Button>
    </main>
  )
}
