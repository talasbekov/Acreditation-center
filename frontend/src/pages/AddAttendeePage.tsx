import { useTranslation } from 'react-i18next'
import { AttendeeForm } from '@/components/AttendeeForm'
import { BackToRegistry, CancelLink } from '@/components/BackToRegistry'
import { PageHeader } from '@/components/ui/form'

/** Страница добавления участника (Story 5.2, вид — эталон этапа D). */
export function AddAttendeePage() {
  const { t } = useTranslation()
  return (
    <div data-ds className="bg-section text-ink">
      <div className="mx-auto max-w-3xl px-4 py-6 md:px-8 md:py-8">
        <BackToRegistry />
        <PageHeader title={t('operatorForm:page.add_title')} context={t('operatorForm:page.add_context')} />
        <AttendeeForm cancel={<CancelLink />} />
      </div>
    </div>
  )
}
