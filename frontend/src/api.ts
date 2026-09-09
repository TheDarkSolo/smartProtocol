export type PublicConfig = {
  document_price_kzt: number
  mrp_kzt: number
  mrp_effective_from: string
  max_upload_bytes: number
  allowed_mime: string[]
}

export type CaseCreated = {
  case_id: string
  status: string
  filename: string
  size_bytes: number
  created_at: string
}

/** Значения на случай, если бэкенд не поднят: лендинг обязан рендериться всегда. */
export const FALLBACK_CONFIG: PublicConfig = {
  document_price_kzt: 2990,
  mrp_kzt: 3932,
  mrp_effective_from: '2025-01-01',
  max_upload_bytes: 15 * 1024 * 1024,
  allowed_mime: ['application/pdf', 'image/jpeg', 'image/png', 'image/heic'],
}

export async function fetchConfig(signal?: AbortSignal): Promise<PublicConfig> {
  const response = await fetch('/api/config', { signal })
  if (!response.ok) throw new Error(`config: ${response.status}`)
  return response.json()
}

export class ApiError extends Error {
  constructor(message: string, readonly offline = false) {
    super(message)
    this.name = 'ApiError'
  }
}

export async function uploadCase(file: File): Promise<CaseCreated> {
  const body = new FormData()
  body.append('file', file)

  let response: Response
  try {
    response = await fetch('/api/cases', { method: 'POST', body })
  } catch {
    throw new ApiError('network', true)
  }

  if (!response.ok) {
    // Бэкенд отдаёт человекочитаемый detail — показываем его как есть.
    const detail = await response
      .json()
      .then((data) => (typeof data?.detail === 'string' ? data.detail : null))
      .catch(() => null)
    throw new ApiError(detail ?? 'failed')
  }

  return response.json()
}
