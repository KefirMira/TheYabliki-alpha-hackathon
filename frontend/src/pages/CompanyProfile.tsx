import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import { getCompanyProfile } from '@/store/service/Company/getCompanyProfile'
import AboutCompany from '@/widgets/Company/AboutCompany'
import CompanyFields from '@/widgets/Company/CompanyFields'
import {
  FeedMessage,
  NoCompanyMessage,
  RetryButton,
} from '@/widgets/Insights/FeedStates'
import PageHeading from '@/widgets/Layout/PageHeading'

/** Профиль компании: что Пульс знает о компании из данных банка. */
const CompanyProfile = () => {
  const dispatch = useAppDispatch()
  const { currentCompanyId, profile, loading, error } = useAppSelector(
    (state) => state.company
  )

  const content = (() => {
    if (profile) {
      return (
        <>
          <AboutCompany profile={profile} />
          <CompanyFields profile={profile} />
        </>
      )
    }
    if (error) {
      return (
        <FeedMessage
          error
          title="Профиль не загрузился"
          text={error}
          action={
            currentCompanyId && (
              <RetryButton
                onClick={() => dispatch(getCompanyProfile(currentCompanyId))}
              />
            )
          }
        />
      )
    }
    if (loading || currentCompanyId) {
      return (
        <div className="flex flex-col gap-4" aria-busy="true">
          <div className="h-[120px] animate-pulse rounded-[20px] bg-white" />
          <div className="h-[220px] animate-pulse rounded-[20px] bg-white" />
        </div>
      )
    }
    return <NoCompanyMessage />
  })()

  return (
    <>
      <PageHeading
        title="Профиль компании"
        subtitle="Что Пульс знает о компании и откуда эти данные"
      />
      {content}
    </>
  )
}

export default CompanyProfile
