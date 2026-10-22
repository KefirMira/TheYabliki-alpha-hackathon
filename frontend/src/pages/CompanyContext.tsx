import { useFlash } from '@/hooks/useFlash'
import { FEATURES } from '@/shared/constants/features'
import FlashMessage from '@/shared/ui/FlashMessage'
import ContextApiCard from '@/widgets/Company/ContextApiCard'
import ContextFiles from '@/widgets/Company/ContextFiles'
import ContextNotes from '@/widgets/Company/ContextNotes'
import PageHeading from '@/widgets/Layout/PageHeading'

/**
 * Контекст: то, чего нет в данных банка, — файлы, сведения, будущий API.
 * Пока API нет, файлы и сведения скрыты (FEATURES.companyContext): иначе
 * интерфейс обещал бы учесть то, что на сервер не уходит.
 */
const CompanyContext = () => {
  const [message, flash] = useFlash()

  return (
    <>
      <PageHeading
        title="Контекст"
        subtitle={
          FEATURES.companyContext
            ? 'Дополните то, чего нет в данных банка — так оценки влияния станут точнее'
            : 'Как Пульс сможет учитывать то, чего нет в данных банка'
        }
      />
      {FEATURES.companyContext && (
        <>
          <ContextFiles />
          <ContextNotes onSaved={flash} />
        </>
      )}
      <ContextApiCard />
      <FlashMessage message={message} />
    </>
  )
}

export default CompanyContext
