import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export const cn = (...i: ClassValue[]) => twMerge(clsx(i))

/** Display-only formatting. All money amounts come from the server in minor units (pesewas). */
export function money(minor: number | null | undefined, currency = 'GHS') {
  if (minor == null) return '—'
  return new Intl.NumberFormat('en-GH', { style: 'currency', currency }).format(minor / 100)
}
/** Convert a form input (e.g. "250.50") to minor units. Input handling only, never used for totals. */
export const toMinor = (v: string | number) => Math.round(Number(v || 0) * 100)
export const fromMinor = (m: number | null | undefined) => (m == null ? '' : String(m / 100))

export function fmtDate(d?: string | null) {
  if (!d) return '—'
  const dt = new Date(d.length === 10 ? d + 'T00:00:00' : d)
  return dt.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}
export function fmtDateTime(d?: string | null) {
  if (!d) return '—'
  return new Date(d).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}
export const isoToday = () => new Date().toISOString().slice(0, 10)
export const addDays = (iso: string, n: number) => {
  const d = new Date(iso + 'T00:00:00Z')
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}
export const titleCase = (s: string) => s.replace(/[_-]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
