/** Compact, readable text for tool results: what a model (and a person reading the transcript) needs. */
import type { Contact, DashboardStats, Deal, PipelineColumn, Property } from './api.js'

const aud = new Intl.NumberFormat('en-AU', { style: 'currency', currency: 'AUD', maximumFractionDigits: 0 })

export const money = (v: number | null | undefined): string => (v === null || v === undefined ? 'n/a' : aud.format(v))

export function budget(min: number | null, max: number | null): string {
  if (min !== null && max !== null) return `${money(min)}–${money(max)}`
  if (min !== null) return `${money(min)}+`
  if (max !== null) return `up to ${money(max)}`
  return 'no budget set'
}

export function contactLine(c: Contact): string {
  const reach = [c.email, c.phone].filter(Boolean).join(', ') || 'no contact details'
  return `- ${c.name} (contact #${c.id}, ${c.type}) · budget ${budget(c.budget_min, c.budget_max)} · ${reach}`
}

export function propertyLine(p: Property): string {
  const rooms = `${p.bedrooms ?? '?'} bed / ${p.bathrooms ?? '?'} bath / ${p.parking ?? '?'} car`
  return `- ${p.title} (property #${p.id}) · ${p.address_line}, ${p.suburb} ${p.state} · ${p.type}, ${p.status} · ${money(p.price)} · ${rooms}`
}

export function list<T>(items: T[], total: number, noun: string, line: (item: T) => string): string {
  if (items.length === 0) return `No ${noun} found.`
  const more = total > items.length ? ` (showing ${items.length} of ${total}; narrow the search for more)` : ''
  return `${total} ${noun}${more}:\n${items.map(line).join('\n')}`
}

export function dealDetail(d: Deal): string {
  const lines = [
    `${d.title} (deal #${d.id})`,
    `Stage: ${d.stage_label} · Value: ${money(d.value)} · Expected close: ${d.expected_close_date ?? 'n/a'}`,
    `Contact: ${d.contact ? `${d.contact.name} (contact #${d.contact.id})` : 'n/a'}`,
    `Property: ${d.property ? `${d.property.title}, ${d.property.suburb} (property #${d.property.id})` : 'none'}`,
    `Agent: ${d.agent?.name ?? 'unassigned'}`,
  ]
  if (d.notes) lines.push(`Notes: ${d.notes}`)
  if (d.activities?.length) {
    lines.push('Recent activity:')
    for (const a of d.activities.slice(0, 10)) {
      // Stage-change bodies already read "Stage changed from X to Y".
      lines.push(`- ${a.created_at.slice(0, 10)} ${a.type === 'note' ? 'Note: ' : ''}${a.body ?? ''} (${a.user?.name ?? 'System'})`)
    }
  }
  return lines.join('\n')
}

export function pipelineSummary(columns: PipelineColumn[], dealsPerStage = 5): string {
  return columns
    .map((c) => {
      const head = `${c.label}: ${c.count} deal${c.count === 1 ? '' : 's'}, ${money(c.total_value)}`
      const deals = c.deals
        .slice(0, dealsPerStage)
        .map((d) => `  - ${d.title} (deal #${d.id}) · ${money(d.value)} · ${d.contact?.name ?? 'n/a'}`)
      if (c.deals.length > dealsPerStage) deals.push(`  - …and ${c.deals.length - dealsPerStage} more`)
      return [head, ...deals].join('\n')
    })
    .join('\n')
}

export function stats(s: DashboardStats): string {
  return [
    `Contacts: ${s.contacts}`,
    `Active listings: ${s.active_listings}`,
    `Open deals: ${s.open_deals} worth ${money(s.pipeline_value)}`,
    `Won this month: ${s.won_this_month} worth ${money(s.won_value_this_month)}`,
  ].join('\n')
}
