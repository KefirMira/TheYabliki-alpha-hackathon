import { FEATURES } from '@/shared/constants/features'
import { toast } from '@/shared/ui/appToast'
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
          <ContextNotes onSaved={toast.success} />
        </>
      )}
      <ContextApiCard />
    </>
  )
}

export default CompanyContext
