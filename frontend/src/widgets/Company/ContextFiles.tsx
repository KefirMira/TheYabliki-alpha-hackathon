import { type DragEvent, useEffect, useRef, useState } from 'react'
import { Download, Ellipsis, TriangleAlert, Upload } from 'lucide-react'

import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { cn } from '@/lib/utils'
import {
  CONTEXT_TEMPLATES,
  type FileStatus,
  type IContextFile,
} from '@/shared/mocks/pulse'
import Card from '@/shared/ui/Card'

const ACCEPT = '.csv,.xlsx,.docx,.pdf,.txt'
const MAX_BYTES = 20 * 1024 * 1024
const PROCESSING_MS = 2500

const STATUS_META: Record<FileStatus, { label: string; className: string }> = {
  done: { label: 'Обработан', className: 'bg-tone-opp text-tone-opp-fg' },
  processing: {
    label: 'Обрабатывается…',
    className: 'bg-tone-hyp text-tone-hyp-fg',
  },
  error: { label: 'Ошибка', className: 'bg-tone-risk text-tone-risk-fg' },
}

const formatSize = (bytes: number) =>
  bytes >= 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1).replace('.', ',')} МБ`
    : `${Math.max(1, Math.round(bytes / 1024))} КБ`

const extensionOf = (name: string) =>
  (name.split('.').pop() ?? '').toUpperCase().slice(0, 4)

/** Скачать шаблон CSV: заголовок столбцов, разделитель «;», UTF-8 с BOM. */
const downloadTemplate = (file: string, header: string) => {
  const blob = new Blob([`\uFEFF${header}\n`], {
    type: 'text/csv;charset=utf-8',
  })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = file
  link.click()
  URL.revokeObjectURL(link.href)
}

/**
 * Загрузка файлов контекста. UI-заглушка: файл не отправляется на сервер,
 * разбор имитируется таймером — так виден весь путь статусов.
 */
const ContextFiles = () => {
  const [files, setFiles] = useState<IContextFile[]>([])
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const timers = useRef<number[]>([])

  useEffect(() => () => timers.current.forEach(window.clearTimeout), [])

  const addFiles = (list: FileList | null) => {
    if (!list) return
    const added: IContextFile[] = Array.from(list).map((file, index) => {
      const id = `${Date.now()}-${index}`
      const tooBig = file.size > MAX_BYTES
      if (!tooBig) {
        timers.current.push(
          window.setTimeout(() => {
            setFiles((current) =>
              current.map((item) =>
                item.id === id
                  ? {
                      ...item,
                      status: 'done',
                      note: 'Файл разобран — факты появятся в профиле после проверки',
                    }
                  : item
              )
            )
          }, PROCESSING_MS)
        )
      }
      return {
        id,
        name: file.name,
        meta: `Только что · ${formatSize(file.size)}`,
        status: tooBig ? 'error' : 'processing',
        progress: tooBig ? undefined : 30,
        note: tooBig
          ? 'Файл больше 20 МБ — загрузите файл меньшего размера'
          : undefined,
      }
    })
    setFiles((current) => [...added, ...current])
  }

  const handleDrop = (event: DragEvent) => {
    event.preventDefault()
    setDragOver(false)
    addFiles(event.dataTransfer.files)
  }

  return (
    <Card>
      <h2 className="text-[17px] font-semibold leading-6">Загрузить файлы</h2>

      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={cn(
          'flex flex-col items-center gap-2.5 rounded-2xl border-[1.5px] border-dashed p-7 text-center transition-colors',
          dragOver
            ? 'border-ink bg-white'
            : 'border-line-dashed bg-surface-drop hover:border-ink-4'
        )}
      >
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-page text-ink-2">
          <Upload className="h-5 w-5" />
        </span>
        <span className="text-[15px] font-semibold">
          Перетащите файлы или{' '}
          <span className="text-brand">выберите на компьютере</span>
        </span>
        <span className="text-[13px] text-ink-3">
          CSV, XLSX, DOCX, PDF, TXT · до 20 МБ
        </span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        multiple
        hidden
        onChange={(event) => {
          addFiles(event.target.files)
          event.target.value = ''
        }}
      />

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
        <span className="text-ink-3">Скачать шаблон:</span>
        {CONTEXT_TEMPLATES.map((template) => (
          <button
            key={template.file}
            type="button"
            onClick={() => downloadTemplate(template.file, template.header)}
            className="inline-flex items-center gap-1.5 font-medium hover:text-brand"
          >
            <Download className="h-4 w-4" />
            {template.label}
          </button>
        ))}
      </div>

      <div className="flex flex-col">
        {files.map((file) => {
          const status = STATUS_META[file.status]
          return (
            <div
              key={file.id}
              className="flex flex-col gap-2.5 border-t border-line py-3.5"
            >
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-surface-page font-mono text-[10px] font-medium text-ink-2">
                  {extensionOf(file.name)}
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="truncate text-[15px] font-medium">
                    {file.name}
                  </span>
                  <span className="text-[13px] text-ink-3">{file.meta}</span>
                </span>
                <span
                  className={cn(
                    'whitespace-nowrap rounded-md px-2 py-1 text-xs font-semibold',
                    status.className
                  )}
                >
                  {status.label}
                </span>
                <Popover>
                  <PopoverTrigger
                    aria-label={`Действия с файлом ${file.name}`}
                    className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-2 transition-colors hover:bg-surface-page data-[state=open]:bg-surface-page"
                  >
                    <Ellipsis className="h-5 w-5" />
                  </PopoverTrigger>
                  <PopoverContent className="flex w-44 flex-col p-1.5">
                    <PopoverClose className="rounded-lg px-3 py-2 text-left text-sm hover:bg-surface-page">
                      Скачать
                    </PopoverClose>
                    <PopoverClose
                      onClick={() =>
                        setFiles((current) =>
                          current.filter((item) => item.id !== file.id)
                        )
                      }
                      className="rounded-lg px-3 py-2 text-left text-sm text-tone-risk-fg hover:bg-tone-risk"
                    >
                      Удалить
                    </PopoverClose>
                  </PopoverContent>
                </Popover>
              </div>

              {file.status === 'processing' && (
                <div className="flex flex-col gap-1.5 pl-[52px]">
                  <div className="h-1 overflow-hidden rounded-sm bg-line-soft">
                    <div
                      className="h-1 rounded-sm bg-ink"
                      style={{ width: `${file.progress ?? 0}%` }}
                    />
                  </div>
                  <span className="text-[13px] text-ink-3">
                    Извлекаем факты · {file.progress ?? 0}%
                  </span>
                </div>
              )}
              {file.status === 'done' && file.note && (
                <p className="pl-[52px] text-sm text-ink-2">{file.note}</p>
              )}
              {file.status === 'error' && file.note && (
                <p className="flex items-center gap-2 pl-[52px] text-sm text-tone-risk-fg">
                  <TriangleAlert className="h-4 w-4 shrink-0" />
                  {file.note}
                </p>
              )}
            </div>
          )
        })}
      </div>
    </Card>
  )
}

export default ContextFiles
