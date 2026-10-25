import { ArrowRight, Check, CircleAlert, Loader2, Sparkles } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { useCompanyProfiles } from '@/hooks/useCompanyProfiles'
import { companyNameOf } from '@/shared/api/mappers/companyMappers'
import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import { setCurrentCompany } from '@/store/reducers/CompanySlice'
import { selectUserCompanyIds } from '@/store/selectors/pulse'
import { runAnalysis } from '@/store/service/Insights/runAnalysis'

interface OtherCompaniesAnalysisProps {
  newsId: number
  newsKey: string
  title: string
}

/**
 * Та же новость для остальных компаний логина: она уже в базе, поэтому
 * анализ идёт по её news_id без повторного сохранения. Результат хранится
 * в сторе этой компании — откроется и после переключения на неё.
 */
const OtherCompaniesAnalysis = ({
  newsId,
  newsKey,
  title,
}: OtherCompaniesAnalysisProps) => {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const currentId = useAppSelector((state) => state.company.currentCompanyId)
  const others = useAppSelector(selectUserCompanyIds).filter(
    (id) => id !== currentId
  )
  const runs = useAppSelector((state) => state.analysis.byCompany)
  const profiles = useCompanyProfiles(others)

  if (others.length === 0) return null

  const open = (companyId: string, insightId: number) => {
    dispatch(setCurrentCompany(companyId))
    navigate(`/pulse/insights/${insightId}`)
  }

  return (
    <div className="flex flex-col gap-2.5 border-t border-line pt-3.5">
      <span className="flex flex-col gap-0.5">
        <span className="text-[15px] font-semibold">
          Другие компании вашего логина
        </span>
        <span className="text-[13px] leading-[18px] text-ink-3">
          Новость уже в базе — анализ для каждой компании отдельный
        </span>
      </span>

      {others.map((companyId) => {
        const profile = profiles[companyId]
        const name = profile ? companyNameOf(profile) : companyId
        // Запуск этой компании относится к нашей новости, только если
        // совпал news_id: иначе там чужой, более ранний анализ.
        const stored = runs[companyId]
        const run = stored?.newsId === newsId ? stored : undefined

        return (
          <div
            key={companyId}
            className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5 rounded-[14px] bg-surface-page py-2.5 pl-3.5 pr-2.5"
          >
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-sm font-semibold">{name}</span>
              {run?.status === 'error' && (
                <span className="flex items-center gap-1.5 text-[13px] text-tone-risk-fg">
                  <CircleAlert className="h-3.5 w-3.5 shrink-0" />
                  {run.message}
                </span>
              )}
            </span>

            {run?.status === 'running' ? (
              <span className="flex items-center gap-1.5 px-2 text-[13px] text-ink-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Анализируем…
              </span>
            ) : run?.status === 'done' ? (
              <Button
                variant="ghost"
                onClick={() => open(companyId, run.result.insight_id)}
                className="h-auto px-2.5 py-1.5 text-[13px]"
              >
                <Check className="text-tone-opp-fg" />
                Открыть
                <ArrowRight />
              </Button>
            ) : (
              <Button
                variant="secondary"
                onClick={() =>
                  dispatch(runAnalysis({ companyId, title, newsId, newsKey }))
                }
                className="h-auto bg-white px-2.5 py-1.5 text-[13px]"
              >
                <Sparkles />
                {run?.status === 'error' ? 'Повторить' : 'Проанализировать'}
              </Button>
            )}
          </div>
        )
      })}
    </div>
  )
}

export default OtherCompaniesAnalysis
