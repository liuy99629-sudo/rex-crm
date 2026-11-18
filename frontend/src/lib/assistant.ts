import type { AiToolCall } from '../api/types'
import { formatCurrency } from './format'

const LABELS: Record<string, string> = {
  semantic_search: 'Searched notes and descriptions',
  search_properties: 'Filtered listings',
  search_contacts: 'Filtered contacts',
  get_deal: 'Opened deal',
  pipeline_summary: 'Read pipeline totals',
}

const MONEY_KEYS = new Set(['min_price', 'max_price', 'can_afford'])

/** Human-readable line for one assistant lookup, e.g. "Filtered listings: suburb Burwood, max price $1,000,000". */
export function describeToolCall(call: AiToolCall): string {
  const label = LABELS[call.tool] ?? call.tool
  const parts = Object.entries(call.input)
    .filter(([, v]) => v !== null && v !== undefined && v !== '')
    .map(([k, v]) => {
      const key = k.replace(/_/g, ' ')
      if (k === 'query') return `"${String(v)}"`
      if (k === 'deal_id') return `#${String(v)}`
      if (MONEY_KEYS.has(k) && typeof v === 'number') return `${key} ${formatCurrency(v)}`
      return `${key} ${Array.isArray(v) ? v.join(', ') : String(v)}`
    })
  const text = parts.length ? `${label}: ${parts.join(', ')}` : label
  return call.error ? `${text} (failed)` : text
}
