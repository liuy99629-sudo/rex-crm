import type { AiToolCall } from '../api/types'
import { formatCurrency } from './format'

const LABELS: Record<string, string> = {
  semantic_search: 'Searched notes and descriptions',
  match_buyers_for_property: 'Matched buyers to listing',
  match_listings_for_contact: 'Matched listings to client',
  search_properties: 'Filtered listings',
  search_contacts: 'Filtered contacts',
  get_deal: 'Opened deal',
  pipeline_summary: 'Read pipeline totals',
}

const MONEY_KEYS = new Set(['min_price', 'max_price', 'can_afford'])

/** Colour band for a 0..100 match score. */
export function matchTier(score: number): 'high' | 'mid' | 'low' {
  return score >= 70 ? 'high' : score >= 45 ? 'mid' : 'low'
}

/** "62%" plus a colour band for a 0..1 win probability. */
export function winChance(p: number): { text: string; tier: 'high' | 'mid' | 'low' } {
  const pct = Math.round(p * 100)
  return { text: `${pct}%`, tier: pct >= 60 ? 'high' : pct >= 30 ? 'mid' : 'low' }
}

/** Human-readable line for one assistant lookup, e.g. "Filtered listings: suburb Burwood, max price $1,000,000". */
export function describeToolCall(call: AiToolCall): string {
  const label = LABELS[call.tool] ?? call.tool
  const parts = Object.entries(call.input)
    .filter(([, v]) => v !== null && v !== undefined && v !== '')
    .map(([k, v]) => {
      const key = k.replace(/_/g, ' ')
      if (k === 'query') return `"${String(v)}"`
      if (k === 'deal_id' || k === 'property_id' || k === 'contact_id') return `#${String(v)}`
      if (MONEY_KEYS.has(k) && typeof v === 'number') return `${key} ${formatCurrency(v)}`
      return `${key} ${Array.isArray(v) ? v.join(', ') : String(v)}`
    })
  const text = parts.length ? `${label}: ${parts.join(', ')}` : label
  return call.error ? `${text} (failed)` : text
}
