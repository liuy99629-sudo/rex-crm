import { describe, expect, it } from 'vitest'
import { ago, days, monthLabel, num, percent } from './insights'

describe('insights helpers', () => {
  it('reads numbers that arrive as strings', () => {
    expect(num('0.667')).toBe(0.667)
    expect(num(null)).toBeNull()
    expect(percent('0.667')).toBe('67%')
    expect(percent(null)).toBe('–')
    expect(days(12.5)).toBe('12.5 d')
  })

  it('labels months and freshness', () => {
    expect(monthLabel('2026-11-01 00:00:00')).toBe('Nov 2026')
    const now = new Date('2026-11-19T06:00:00Z')
    expect(ago('2026-11-19 03:00:00', now)).toBe('3 h ago')
    expect(ago('2026-11-19T03:00:00+00:00', now)).toBe('3 h ago') // what the API returns
    expect(ago('2026-11-19T05:59:30Z', now)).toBe('just now')
    expect(ago(null, now)).toBe('never')
  })
})
