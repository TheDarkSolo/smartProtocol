import { useRef, useState } from 'react'
import { useI18n, fill } from '../i18n'
import { ApiError, uploadCase, type CaseCreated, type PublicConfig } from '../api'
import { IconUpload, IconDone } from './icons'

export function UploadCard({ config }: { config: PublicConfig }) {
  const { t } = useI18n()
  const inputRef = useRef<HTMLInputElement>(null)
  const [isOver, setIsOver] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<CaseCreated | null>(null)

  async function send(file: File) {
    setError(null)
    setIsSending(true)
    try {
      setCreated(await uploadCase(file))
    } catch (cause) {
      if (cause instanceof ApiError) {
        // Бэкенд прислал понятную причину — показываем её, а не общий текст.
        setError(
          cause.offline
            ? t.upload.errorOffline
            : cause.message === 'failed'
              ? t.upload.errorGeneric
              : cause.message,
        )
      } else {
        setError(t.upload.errorGeneric)
      }
    } finally {
      setIsSending(false)
    }
  }

  function reset() {
    setCreated(null)
    setError(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  if (created) {
    return (
      <div className="upload">
        <div className="upload-success">
          <div className="upload-success-mark">
            <IconDone />
          </div>
          <h3>{t.upload.successTitle}</h3>
          <p>{t.upload.successBody}</p>
          <div className="case-id">
            {t.upload.caseId}: {created.case_id}
          </div>
          <button type="button" className="btn btn-ghost" onClick={reset}>
            {t.upload.another}
          </button>
        </div>
      </div>
    )
  }

  const maxMb = Math.round(config.max_upload_bytes / (1024 * 1024))

  return (
    <div className="upload">
      <h2>{t.upload.title}</h2>
      <p className="upload-hint">{t.upload.hint}</p>

      <div
        className={`dropzone${isOver ? ' is-over' : ''}`}
        onDragOver={(event) => {
          event.preventDefault()
          setIsOver(true)
        }}
        onDragLeave={() => setIsOver(false)}
        onDrop={(event) => {
          event.preventDefault()
          setIsOver(false)
          const file = event.dataTransfer.files?.[0]
          if (file) void send(file)
        }}
      >
        <div className="dropzone-icon">
          <IconUpload />
        </div>

        <button
          type="button"
          className="btn"
          disabled={isSending}
          onClick={() => inputRef.current?.click()}
        >
          {isSending ? t.upload.sending : isOver ? t.upload.drop : t.upload.button}
        </button>

        <p className="dropzone-formats">{fill(t.upload.formats, { size: maxMb })}</p>

        <input
          ref={inputRef}
          type="file"
          hidden
          accept={config.allowed_mime.join(',')}
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) void send(file)
          }}
        />
      </div>

      {error && (
        <p className="upload-error" role="alert">
          {error}
        </p>
      )}
      <p className="upload-free">{t.upload.freeNote}</p>
    </div>
  )
}
