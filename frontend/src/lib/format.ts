const aud = new Intl.NumberFormat('en-AU', {
  style: 'currency',
  currency: 'AUD',
  maximumFractionDigits: 0,
})

export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-'
  return aud.format(value)
}

/** Budget range with open ends: "$500,000+", "Up to $800,000", "$500,000 - $800,000", or "-". */
export function formatBudget(min: number | null | undefined, max: number | null | undefined): string {
  const hasMin = min !== null && min !== undefined
  const hasMax = max !== null && max !== undefined
  if (hasMin && hasMax) return `${formatCurrency(min)} - ${formatCurrency(max)}`
  if (hasMin) return `${formatCurrency(min)}+`
  if (hasMax) return `Up to ${formatCurrency(max)}`
  return '-'
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '-'
  return d.toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '-'
  return d.toLocaleString('en-AU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

/** "under_offer" -> "Under offer" */
export function humanize(value: string): string {
  const text = value.replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** Empty string -> null, otherwise a number. Used for optional numeric inputs. */
export function toNumberOrNull(value: string): number | null {
  if (value.trim() === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

/** Empty string -> null. */
export function toStringOrNull(value: string): string | null {
  return value.trim() === '' ? null : value.trim()
}
