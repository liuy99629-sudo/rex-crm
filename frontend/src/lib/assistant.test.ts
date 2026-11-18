import { describe, expect, it } from 'vitest'
import { describeToolCall } from './assistant'

describe('describeToolCall', () => {
  it('lists only the filters that were set, with money formatted', () => {
    const line = describeToolCall({
      tool: 'search_properties',
      input: { suburb: 'Burwood', min_price: null, max_price: 1_000_000, min_bedrooms: 3, status: null, type: null },
      error: false,
    })
    expect(line).toBe('Filtered listings: suburb Burwood, max price $1,000,000, min bedrooms 3')
  })

  it('quotes semantic queries, shows deal ids and flags failures', () => {
    expect(describeToolCall({ tool: 'semantic_search', input: { query: 'wants a pool', kinds: ['contact'] }, error: false })).toBe(
      'Searched notes and descriptions: "wants a pool", kinds contact',
    )
    expect(describeToolCall({ tool: 'get_deal', input: { deal_id: 7 }, error: true })).toBe('Opened deal: #7 (failed)')
    expect(describeToolCall({ tool: 'pipeline_summary', input: {}, error: false })).toBe('Read pipeline totals')
  })
})

describe('score bands', () => {
  it('bands match scores and win chances', async () => {
    const { matchTier, winChance } = await import('./assistant')
    expect([matchTier(85), matchTier(50), matchTier(20)]).toEqual(['high', 'mid', 'low'])
    expect(winChance(0.624)).toEqual({ text: '62%', tier: 'high' })
    expect(winChance(0.3).tier).toBe('mid')
    expect(winChance(0.05)).toEqual({ text: '5%', tier: 'low' })
  })

  it('describes matching lookups with ids', () => {
    expect(describeToolCall({ tool: 'match_buyers_for_property', input: { property_id: 4 }, error: false })).toBe(
      'Matched buyers to listing: #4',
    )
  })
})
