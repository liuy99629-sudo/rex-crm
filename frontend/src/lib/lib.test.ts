import { describe, expect, it } from 'vitest'
import type { Deal, PipelineColumn } from '../api/types'
import { formatBudget, formatCurrency, humanize, toNumberOrNull } from './format'
import { moveDeal } from './pipeline'

const deal = (id: number, stage: Deal['stage'], value: number): Deal => ({
  id,
  title: `Deal ${id}`,
  stage,
  stage_label: stage,
  value,
  expected_close_date: null,
  notes: null,
  contact_id: 1,
  property_id: null,
})

const column = (stage: PipelineColumn['stage'], deals: Deal[]): PipelineColumn => ({
  stage,
  label: stage,
  count: deals.length,
  total_value: deals.reduce((s, d) => s + d.value, 0),
  deals,
})

describe('format helpers', () => {
  it('formats AUD without decimals', () => {
    expect(formatCurrency(1250000)).toContain('1,250,000')
    expect(formatCurrency(null)).toBe('-')
  })

  it('formats budget ranges with open ends', () => {
    expect(formatBudget(500000, 800000)).toMatch(/500,000 - .*800,000/)
    expect(formatBudget(500000, null)).toMatch(/500,000\+$/)
    expect(formatBudget(null, 800000)).toMatch(/^Up to .*800,000/)
    expect(formatBudget(null, null)).toBe('-')
    expect(formatBudget(0, null)).toMatch(/0\+$/)
  })

  it('humanizes snake_case', () => {
    expect(humanize('under_offer')).toBe('Under offer')
  })

  it('parses optional numbers', () => {
    expect(toNumberOrNull('')).toBeNull()
    expect(toNumberOrNull('42')).toBe(42)
    expect(toNumberOrNull('abc')).toBeNull()
  })
})

describe('moveDeal', () => {
  it('moves a deal between columns and recomputes totals', () => {
    const board = [
      column('lead', [deal(1, 'lead', 100), deal(2, 'lead', 200)]),
      column('offer', [deal(3, 'offer', 500)]),
    ]

    const next = moveDeal(board, 1, 'offer')

    expect(next[0].count).toBe(1)
    expect(next[0].total_value).toBe(200)
    expect(next[1].count).toBe(2)
    expect(next[1].total_value).toBe(600)
    expect(next[1].deals[0].id).toBe(1)
    expect(next[1].deals[0].stage).toBe('offer')
  })

  it('returns the same board when the stage does not change', () => {
    const board = [column('lead', [deal(1, 'lead', 100)])]
    expect(moveDeal(board, 1, 'lead')).toBe(board)
  })
})
