import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { buttonVariants } from '@/components/ui/button'
import { registryState } from '@/lib/registryState'

/** «К списку участников» — возврат в реестр с теми же фильтром и страницей (этап D). */
export function BackToRegistry() {
  const { t } = useTranslation()
  return (
    <Link
      to={registryState.get().listUrl}
      className="mb-3 inline-flex min-h-11 items-center font-semibold text-primary underline-offset-2 hover:underline"
    >
      {t('operatorForm:back')}
    </Link>
  )
}

/** «Отмена» рядом с кнопкой сохранения: туда же, в ту же выборку реестра. */
export function CancelLink() {
  const { t } = useTranslation()
  return (
    <Link to={registryState.get().listUrl} className={buttonVariants({ variant: 'secondary' })}>
      {t('operatorForm:cancel')}
    </Link>
  )
}
