/** Helpers for the Insights page (unit-tested). */

/** DB numerics can arrive as strings; null stays null. */
export const num = (v: unknown): number | null => (v === null || v === undefined || v === '' ? null : Number(v))

export const percent = (v: unknown): string => {
  const n = num(v)
  return n === null ? '–' : `${Math.round(n * 100)}%`
}

export const days = (v: unknown): string => {
  const n = num(v)
  return n === null ? '–' : `${n} d`
}

/** "2026-11-01" or "2026-11-01 00:00:00" -> "Nov 2026" */
export const monthLabel = (v: string): string =>
  new Date(`${v.slice(0, 10)}T00:00:00Z`).toLocaleDateString('en-AU', { month: 'short', year: 'numeric', timeZone: 'UTC' })

/** How long ago the job ran, for "Updated 3 hours ago". */
export function ago(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return 'never'
  const then = new Date(iso.includes('T') ? iso : `${iso.replace(' ', 'T')}Z`)
  const mins = Math.floor((now.getTime() - then.getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hours = Math.round(mins / 60)
  if (hours < 48) return `${hours} h ago`
  return `${Math.round(hours / 24)} days ago`
}
