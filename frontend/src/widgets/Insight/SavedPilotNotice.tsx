import type { IInsightDetail } from '@/store/models/IPulse'
import Card from '@/shared/ui/Card'
export const SavedPilotNotice = ({ detail }: { detail: IInsightDetail }) => {
  const pilot = detail.savedPilot
  if (!pilot && detail.collectionPilot) {
    const collection = detail.collectionPilot
    return <Card>
      <h2 className="text-lg font-semibold">Синтетический пример</h2>
      <p>{collection.mode === 'FAKE_TEST_ONLY'
        ? 'Технический fake SDK тест — это не настоящий ответ LLM.'
        : `Сохранённый настоящий ответ ${collection.model}. Нового LLM-вызова при просмотре нет.`}</p>
      <p>Сценарий: {collection.scenarioId}. Генерация: {collection.generatedAt}. Импорт: {collection.importedAt}.</p>
      <p>Компании и новости синтетические. Источники — исторические публичные фрагменты в TXT, не позиция Альфа-Банка и не подтверждение текущих событий. Наличие ссылки не доказывает вывод.</p>
      <p className="font-semibold">Финансовая достоверность не подтверждена</p>
      {collection.usage && <p>Сохранённый usage: вход {collection.usage.prompt_tokens}; выход {collection.usage.completion_tokens}, включая reasoning {collection.usage.reasoning_tokens ?? 'не сообщён'}; всего {collection.usage.total_tokens}.</p>}
      {collection.expertNotes.length > 0 && <div><h3>Оговорки экспертного просмотра</h3><ul>{collection.expertNotes.map((note, i) => <li key={i}>{note}</li>)}</ul></div>}
      <details><summary>Сохранённый журнал анализа ({collection.events.length} шагов)</summary>
        <p>Исторический trace, при импорте и просмотре инструменты не запускались.</p>
        <ol>{collection.events.map((event, i) => <li key={i}>{event.tool} · {event.reason}</li>)}</ol>
        <p className="break-all">SHA-256 исходного ответа: {collection.contentSha256}</p>
      </details>
    </Card>
  }
  if (!pilot) return null
  return (
    <Card>
      <h2 className="text-lg font-semibold">Синтетический пример</h2>
      <p>
        Сохранённый настоящий ответ {pilot.model} от {pilot.pilotDate}. Повторного запроса
        к модели не было.
      </p>
      <p>Источники — учебные TXT, не аналитика Альфа-Банка.</p>
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
