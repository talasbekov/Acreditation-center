import { AttendeeForm } from '@/components/AttendeeForm'

/** Страница добавления участника (Story 5.2). */
export function AddAttendeePage() {
  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="mb-6 text-2xl font-semibold text-neutral-900">
        Добавить участника
      </h1>
      <AttendeeForm />
    </div>
  )
}
