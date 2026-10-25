import type { IInsightDetail } from '@/store/models/IPulse'
import Card from '@/shared/ui/Card'
export const SavedPilotNotice = ({ detail }: { detail: IInsightDetail }) => {
  const pilot = detail.savedPilot
  if (!pilot) return null
  return (
    <Card>
      <h2 className="text-lg font-semibold">Синтетический пример</h2>
      <p>
        Сохранённый ответ {pilot.model} от {pilot.pilotDate}. Повторного запроса
        к модели не было.
      </p>
      <p className="font-semibold">Финансовая достоверность не подтверждена</p>
      <p>
        JSON и происхождение фрагментов проверены технически; это не
        подтверждение финансовых выводов.
      </p>
      <p>
        Время исторического запуска: {pilot.duration.toLocaleString('ru-RU')} с.
        Вход: {pilot.usage.prompt_tokens}; выход:{' '}
        {pilot.usage.completion_tokens}, включая reasoning:{' '}
        {pilot.usage.reasoning_tokens}; всего: {pilot.usage.total_tokens}{' '}
        токенов.
      </p>
      <p>
        Запись импортирована: {pilot.importedAt}. Эта дата не является датой
        нового анализа.
      </p>
      <details>
        <summary>
          Сохранённый журнал пилота ({pilot.events.length} шагов)
        </summary>
        <p>Исторический trace; инструменты сейчас не запускались.</p>
        <ol>
          {pilot.events.map((event, i) => (
            <li key={i}>
              {event.tool} · {event.reason}
            </li>
          ))}
        </ol>
        <p className="break-all">
          SHA-256 импортируемого fixture: {pilot.artifactSha256}
        </p>
      </details>
    </Card>
  )
}
