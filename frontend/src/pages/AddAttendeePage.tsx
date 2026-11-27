import { AttendeeForm } from '@/components/AttendeeForm'
import { BackToRegistry, CancelLink } from '@/components/BackToRegistry'
import { PageHeader } from '@/components/ui/form'

/** Страница добавления участника (Story 5.2, вид — эталон этапа D). */
export function AddAttendeePage() {
  return (
    <main data-ds className="min-h-svh bg-section text-ink">
      <div className="mx-auto max-w-3xl px-4 py-6 md:px-8 md:py-8">
        <BackToRegistry />
        <PageHeader title="Добавить участника" context="Участник попадает в выбранную заявку как черновик." />
        <AttendeeForm cancel={<CancelLink />} />
      </div>
    </main>
  )
}
