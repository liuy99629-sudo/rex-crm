/** Listing types, GraphQL documents and search-parameter parsing (pure: unit-tested). */

export type PropertyType = 'HOUSE' | 'APARTMENT' | 'TOWNHOUSE' | 'LAND' | 'COMMERCIAL'
export const PROPERTY_TYPES: PropertyType[] = ['HOUSE', 'APARTMENT', 'TOWNHOUSE', 'LAND', 'COMMERCIAL']

export interface ListingCard {
  id: string
  title: string
  suburb: string
  state: string
  type: PropertyType
  status: 'ACTIVE' | 'UNDER_OFFER'
  priceLabel: string
  bedrooms: number | null
  bathrooms: number | null
  parking: number | null
}

export interface ListingDetail extends ListingCard {
  address: string
  postcode: string
  landSizeSqm: number | null
  description: string | null
  listedAt: string | null
  agentName: string | null
  similar: ListingCard[]
}

const CARD_FIELDS = 'id title suburb state type status priceLabel bedrooms bathrooms parking'

export const LISTINGS_QUERY = /* GraphQL */ `
  query Listings($filter: ListingFilter, $page: Int) {
    listings(filter: $filter, page: $page, perPage: 12) { total page lastPage items { ${CARD_FIELDS} } }
  }
`

export const LISTING_QUERY = /* GraphQL */ `
  query Listing($id: ID!) {
    listing(id: $id) {
      ${CARD_FIELDS} address postcode landSizeSqm description listedAt agentName
      similar(limit: 3) { ${CARD_FIELDS} }
    }
  }
`

export const ENQUIRY_MUTATION = /* GraphQL */ `
  mutation Enquire($input: EnquiryInput!) { submitEnquiry(input: $input) { reference message } }
`

export interface ListingFilter {
  query?: string
  suburb?: string
  type?: PropertyType
  minPrice?: number
  maxPrice?: number
  minBedrooms?: number
}

type Params = Record<string, string | string[] | undefined>

const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v)?.trim() || undefined
const int = (v: string | string[] | undefined) => {
  const n = Number(one(v))
  return Number.isInteger(n) && n >= 0 ? n : undefined
}

/** URL search params (?q=&type=HOUSE&max=1500000&beds=3&page=2) → GraphQL filter + page. Invalid values are ignored. */
export function parseSearch(params: Params): { filter: ListingFilter; page: number } {
  const type = one(params.type)?.toUpperCase() as PropertyType | undefined
  const filter: ListingFilter = {
    query: one(params.q),
    suburb: one(params.suburb),
    type: type && PROPERTY_TYPES.includes(type) ? type : undefined,
    minPrice: int(params.min),
    maxPrice: int(params.max),
    minBedrooms: int(params.beds),
  }
  for (const k of Object.keys(filter) as (keyof ListingFilter)[]) if (filter[k] === undefined) delete filter[k]
  return { filter, page: Math.max(1, int(params.page) ?? 1) }
}

/** Same search on another page, as a query string. */
export function pageHref(params: Params, page: number): string {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    const val = one(v)
    if (val && k !== 'page') qs.set(k, val)
  }
  if (page > 1) qs.set('page', String(page))
  const s = qs.toString()
  return s ? `/?${s}` : '/'
}

export const typeLabel = (t: PropertyType) => t.charAt(0) + t.slice(1).toLowerCase()

export function features(l: Pick<ListingCard, 'bedrooms' | 'bathrooms' | 'parking'>): string {
  return [
    l.bedrooms !== null && `${l.bedrooms} bed`,
    l.bathrooms !== null && `${l.bathrooms} bath`,
    l.parking !== null && `${l.parking} car`,
  ]
    .filter(Boolean)
    .join(' · ')
}
