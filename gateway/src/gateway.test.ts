import { describe, expect, it } from 'vitest'
import { clientIp, createGateway } from './app.js'
import type { Fetch, ListingDto } from './upstream.js'

const listing = (id: number, over: Partial<ListingDto> = {}): ListingDto => ({
  id,
  title: `Listing ${id}`,
  address_line: `${id} Kent St`,
  suburb: 'Epping',
  state: 'NSW',
  postcode: '2121',
  type: 'house',
  status: 'active',
  price: 1_000_000,
  bedrooms: 3,
  bathrooms: 2,
  parking: 1,
  land_size_sqm: 500,
  description: 'Nice',
  listed_at: '2026-11-01',
  agent_name: 'Agent Amy',
  ...over,
})

interface Seen {
  method: string
  path: string
  query: Record<string, string>
  body: unknown
  forwardedFor: string | null
}

function upstream(handler: (s: Seen) => { status?: number; body: unknown }) {
  const seen: Seen[] = []
  const fetchImpl: Fetch = async (input, init) => {
    const url = new URL(String(input))
    const headers = new Headers(init?.headers)
    const s: Seen = {
      method: init?.method ?? 'GET',
      path: url.pathname,
      query: Object.fromEntries(url.searchParams),
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
      forwardedFor: headers.get('X-Forwarded-For'),
    }
    seen.push(s)
    const r = handler(s)
    return new Response(JSON.stringify(r.body), { status: r.status ?? 200 })
  }
  return { seen, gateway: createGateway('http://crm.test/api', fetchImpl) }
}

async function gql(gateway: ReturnType<typeof createGateway>, query: string, variables?: object, headers: Record<string, string> = {}) {
  const res = await gateway.fetch('http://gw.test/graphql', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: JSON.stringify({ query, variables }),
  })
  return (await res.json()) as { data?: any; errors?: { message: string; extensions?: any }[] }
}

describe('public GraphQL gateway', () => {
  it('lists listings with mapped filters and formatted fields', async () => {
    const { gateway, seen } = upstream(() => ({
      body: { data: [listing(1, { price: null }), listing(2)], meta: { current_page: 1, last_page: 3, total: 25 } },
    }))

    const r = await gql(
      gateway,
      `query($f: ListingFilter) { listings(filter: $f, perPage: 2) { total lastPage items { id type status priceLabel address agentName } } }`,
      { f: { suburb: 'Epping', type: 'HOUSE', maxPrice: 2000000, minBedrooms: 3 } },
      { 'X-Forwarded-For': '203.0.113.7, 10.0.0.1' },
    )

    expect(r.errors).toBeUndefined()
    expect(seen[0].path).toBe('/api/public/listings')
    expect(seen[0].query).toEqual({ suburb: 'Epping', type: 'house', max_price: '2000000', min_bedrooms: '3', page: '1', per_page: '2' })
    expect(seen[0].forwardedFor).toBe('203.0.113.7')
    expect(r.data.listings.total).toBe(25)
    expect(r.data.listings.items[0]).toEqual({ id: '1', type: 'HOUSE', status: 'ACTIVE', priceLabel: 'Contact agent', address: '1 Kent St', agentName: 'Agent Amy' })
    expect(r.data.listings.items[1].priceLabel).toBe('$1,000,000')
  })

  it('returns null for a listing that is not on the market', async () => {
    const { gateway } = upstream(() => ({ status: 404, body: { message: 'Not found.' } }))

    const r = await gql(gateway, `{ listing(id: "9") { id } }`)

    expect(r.errors).toBeUndefined()
    expect(r.data.listing).toBeNull()
  })

  it('resolves similar listings by type and price band, excluding itself', async () => {
    const { gateway, seen } = upstream((s) =>
      s.path.endsWith('/listings/5')
        ? { body: listing(5, { price: 1_200_000 }) }
        : { body: { data: [listing(5), listing(6), listing(7)], meta: { current_page: 1, last_page: 1, total: 3 } } },
    )

    const r = await gql(gateway, `{ listing(id: "5") { id similar(limit: 2) { id } } }`)

    expect(r.data.listing.similar.map((x: { id: string }) => x.id)).toEqual(['6', '7'])
    expect(seen[1].query).toMatchObject({ type: 'house', min_price: '900000', max_price: '1500000', per_page: '3' })
  })

  it('submits an enquiry to the CRM', async () => {
    const { gateway, seen } = upstream(() => ({ status: 201, body: { reference: 'ENQ-00042', message: 'Thanks!' } }))

    const r = await gql(
      gateway,
      `mutation($i: EnquiryInput!) { submitEnquiry(input: $i) { reference message } }`,
      { i: { listingId: '3', name: 'Jane', email: 'jane@example.com', message: 'Is it still available?' } },
    )

    expect(r.data.submitEnquiry).toEqual({ reference: 'ENQ-00042', message: 'Thanks!' })
    expect(seen[0]).toMatchObject({
      method: 'POST',
      path: '/api/public/enquiries',
      body: { listing_id: 3, name: 'Jane', email: 'jane@example.com', phone: null, message: 'Is it still available?', website: null },
    })
  })

  it('maps validation and rate-limit errors to stable codes', async () => {
    let status = 422
    const { gateway } = upstream(() => ({ status, body: { message: 'The email field must be valid.', errors: { email: ['Invalid.'] } } }))
    const send = () =>
      gql(gateway, `mutation { submitEnquiry(input: { listingId: "1", name: "J", email: "x", message: "hi" }) { reference } }`)

    const invalid = await send()
    expect(invalid.errors?.[0].extensions).toMatchObject({ code: 'BAD_USER_INPUT', fields: { email: ['Invalid.'] } })

    status = 429
    expect((await send()).errors?.[0].extensions.code).toBe('RATE_LIMITED')

    status = 500
    const down = await send()
    expect(down.errors?.[0]).toMatchObject({ message: 'The listings service is unavailable.', extensions: { code: 'UPSTREAM_ERROR' } })
  })

  it('masks unexpected errors instead of leaking details', async () => {
    // A malformed upstream record makes a field resolver throw a plain TypeError.
    const { gateway } = upstream(() => ({ body: { ...listing(1), type: undefined } }))

    const r = await gql(gateway, `{ listing(id: "1") { type } }`)

    expect(r.errors?.[0].message).toBe('Unexpected error.')
    expect(JSON.stringify(r.errors)).not.toContain('toUpperCase')
  })

  it('reads the first forwarded IP', () => {
    expect(clientIp(new Headers({ 'x-forwarded-for': '1.2.3.4, 10.0.0.1' }))).toBe('1.2.3.4')
    expect(clientIp(new Headers())).toBeNull()
  })
})
