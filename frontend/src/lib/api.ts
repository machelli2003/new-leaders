const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api/v1'

let accessToken: string | null = null
export const setAccessToken = (t: string | null) => { accessToken = t }
export const getAccessToken = () => accessToken

export class ApiError extends Error {
  status: number
  details?: any
  constructor(status: number, message: string, details?: any) { super(message); this.status = status; this.details = details }
}

let refreshing: Promise<boolean> | null = null
export async function refreshSession(): Promise<any | null> {
  if (!refreshing) {
    refreshing = fetch(`${BASE}/auth/refresh`, { method: 'POST', credentials: 'include', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(async (r) => { if (!r.ok) return null; const d = await r.json(); setAccessToken(d.access_token); return d })
      .catch(() => null)
      .then((d) => { (refreshing as any) = null; return d }) as any
  }
  return (refreshing as any) ?? null
}

type Opts = { method?: string; body?: unknown; form?: FormData; query?: Record<string, any>; auth?: boolean; signal?: AbortSignal }

function qs(q?: Record<string, any>) {
  if (!q) return ''
  const p = new URLSearchParams()
  Object.entries(q).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') p.set(k, String(v)) })
  const s = p.toString()
  return s ? `?${s}` : ''
}

async function send(path: string, o: Opts) {
  const headers: Record<string, string> = {}
  if (accessToken && o.auth !== false) headers.Authorization = `Bearer ${accessToken}`
  let body: BodyInit | undefined
  if (o.form) body = o.form
  else if (o.body !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(o.body) }
  return fetch(`${BASE}${path}${qs(o.query)}`, { method: o.method ?? (body ? 'POST' : 'GET'), headers, body, credentials: 'include', signal: o.signal })
}

async function toError(r: Response) {
  let msg = `Request failed (${r.status})`, details
  try { const j = await r.json(); msg = j?.error?.message ?? j?.detail ?? msg; details = j?.error?.details } catch { /* ignore */ }
  return new ApiError(r.status, msg, details)
}

export async function api<T = any>(path: string, o: Opts = {}): Promise<T> {
  let r = await send(path, o)
  if (r.status === 401 && o.auth !== false && !path.startsWith('/auth/')) {
    const ok = await refreshSession()
    if (ok) r = await send(path, o)
  }
  if (!r.ok) throw await toError(r)
  if (r.status === 204) return undefined as T
  const ct = r.headers.get('content-type') ?? ''
  return (ct.includes('json') ? r.json() : r.text()) as any
}

export async function download(path: string, filename: string, query?: Record<string, any>) {
  let r = await send(path, { query })
  if (r.status === 401) { if (await refreshSession()) r = await send(path, { query }) }
  if (!r.ok) throw await toError(r)
  const blob = await r.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob); a.download = filename; a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}

export const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : e instanceof Error ? e.message : 'Something went wrong')
