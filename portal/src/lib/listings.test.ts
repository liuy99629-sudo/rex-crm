import { describe, expect, it } from 'vitest'
import { features, pageHref, parseSearch, typeLabel } from './listings'

describe('parseSearch', () => {
  it('maps URL params to a GraphQL filter', () => {
    expect(parseSearch({ q: ' pool ', type: 'house', max: '1500000', beds: '3', page: '2' })).toEqual({
      filter: { query: 'pool', type: 'HOUSE', maxPrice: 1500000, minBedrooms: 3 },
      page: 2,
    })
  })

  it('ignores invalid values instead of failing', () => {
    expect(parseSearch({ type: 'castle', max: 'lots', beds: '-1', page: '0' })).toEqual({ filter: {}, page: 1 })
    expect(parseSearch({ q: ['a', 'b'] }).filter).toEqual({ query: 'a' })
  })
})

describe('pageHref', () => {
  it('keeps the search and changes only the page', () => {
    expect(pageHref({ q: 'pool', page: '3' }, 2)).toBe('/?q=pool&page=2')
    expect(pageHref({ q: 'pool', page: '3' }, 1)).toBe('/?q=pool')
    expect(pageHref({}, 1)).toBe('/')
  })
})

describe('display helpers', () => {
  it('formats type and features', () => {
    expect(typeLabel('TOWNHOUSE')).toBe('Townhouse')
    expect(features({ bedrooms: 3, bathrooms: 2, parking: null })).toBe('3 bed · 2 bath')
  })
})
