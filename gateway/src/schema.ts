import { GraphQLError } from 'graphql'
import { createSchema } from 'graphql-yoga'
import { UpstreamError, type CrmPublicApi, type ListingDto } from './upstream.js'

export interface Context {
  crm: CrmPublicApi
}

export const typeDefs = /* GraphQL */ `
  "A property on the market (active or under offer)."
  type Listing {
    id: ID!
    title: String!
    address: String!
    suburb: String!
    state: String!
    postcode: String!
    type: PropertyType!
    status: ListingStatus!
    "Whole Australian dollars; null when the price is withheld."
    price: Int
    "Formatted for display, e.g. \\"$1,250,000\\" or \\"Contact agent\\"."
    priceLabel: String!
    bedrooms: Int
    bathrooms: Int
    parking: Int
    landSizeSqm: Int
    description: String
    listedAt: String
    agentName: String
    "Other listings of the same type at a similar price (within 25%)."
    similar(limit: Int = 3): [Listing!]!
  }

  enum PropertyType { HOUSE APARTMENT TOWNHOUSE LAND COMMERCIAL }
  enum ListingStatus { ACTIVE UNDER_OFFER }

  input ListingFilter {
    "Free text: title, address or suburb."
    query: String
    suburb: String
    type: PropertyType
    minPrice: Int
    maxPrice: Int
    minBedrooms: Int
  }

  type ListingPage {
    items: [Listing!]!
    total: Int!
    page: Int!
    lastPage: Int!
  }

  input EnquiryInput {
    listingId: ID!
    name: String!
    email: String!
    phone: String
    message: String!
    "Honeypot; leave empty."
    website: String
  }

  type EnquiryResult {
    reference: String!
    message: String!
  }

  type Query {
    listings(filter: ListingFilter, page: Int = 1, perPage: Int = 12): ListingPage!
    listing(id: ID!): Listing
  }

  type Mutation {
    "Send an enquiry to the listing agent. It arrives in the CRM as a new lead."
    submitEnquiry(input: EnquiryInput!): EnquiryResult!
  }
`

/** Error codes the portal may see; any other error is masked by the server. */
export const PUBLIC_ERROR_CODES = new Set(['BAD_USER_INPUT', 'NOT_FOUND', 'RATE_LIMITED', 'UPSTREAM_ERROR'])

const aud = new Intl.NumberFormat('en-AU', { style: 'currency', currency: 'AUD', maximumFractionDigits: 0 })

/** Map CRM failures to GraphQL errors with stable codes the portal can switch on. */
function toGraphQLError(err: unknown): never {
  if (err instanceof UpstreamError) {
    if (err.status === 422) {
      throw new GraphQLError(err.message, { extensions: { code: 'BAD_USER_INPUT', fields: err.errors } })
    }
    if (err.status === 404) throw new GraphQLError('This listing is no longer available.', { extensions: { code: 'NOT_FOUND' } })
    if (err.status === 429) {
      throw new GraphQLError('Too many enquiries, please try again in a minute.', { extensions: { code: 'RATE_LIMITED' } })
    }
  }
  throw new GraphQLError('The listings service is unavailable.', { extensions: { code: 'UPSTREAM_ERROR' } })
}

export const schema = createSchema<Context>({
  typeDefs,
  resolvers: {
    Query: {
      listings: async (_: unknown, args: { filter?: Record<string, unknown> | null; page: number; perPage: number }, { crm }: Context) => {
        const f = args.filter ?? {}
        try {
          const res = await crm.listings({
            q: f.query,
            suburb: f.suburb,
            type: typeof f.type === 'string' ? f.type.toLowerCase() : undefined,
            min_price: f.minPrice,
            max_price: f.maxPrice,
            min_bedrooms: f.minBedrooms,
            page: Math.max(1, args.page),
            per_page: Math.min(Math.max(1, args.perPage), 50),
          })
          return { items: res.data, total: res.meta.total, page: res.meta.current_page, lastPage: res.meta.last_page }
        } catch (err) {
          return toGraphQLError(err)
        }
      },
      listing: async (_: unknown, { id }: { id: string }, { crm }: Context) => {
        const n = Number(id)
        if (!Number.isInteger(n) || n < 1) return null
        try {
          return await crm.listing(n)
        } catch (err) {
          return toGraphQLError(err)
        }
      },
    },
    Mutation: {
      submitEnquiry: async (_: unknown, { input }: { input: Record<string, unknown> }, { crm }: Context) => {
        try {
          return await crm.enquire({
            listing_id: Number(input.listingId),
            name: input.name,
            email: input.email,
            phone: input.phone || null,
            message: input.message,
            website: input.website || null,
          })
        } catch (err) {
          return toGraphQLError(err)
        }
      },
    },
    Listing: {
      address: (l: ListingDto) => l.address_line,
      type: (l: ListingDto) => l.type.toUpperCase(),
      status: (l: ListingDto) => l.status.toUpperCase(),
      priceLabel: (l: ListingDto) => (l.price === null ? 'Contact agent' : aud.format(l.price)),
      landSizeSqm: (l: ListingDto) => l.land_size_sqm,
      listedAt: (l: ListingDto) => l.listed_at,
      agentName: (l: ListingDto) => l.agent_name ?? null,
      similar: async (l: ListingDto, { limit }: { limit: number }, { crm }: Context) => {
        const take = Math.min(Math.max(limit, 0), 10)
        if (take === 0) return []
        const query: Record<string, unknown> = { type: l.type, per_page: take + 1 }
        if (l.price !== null) {
          query.min_price = Math.round(l.price * 0.75)
          query.max_price = Math.round(l.price * 1.25)
        }
        try {
          const res = await crm.listings(query)
          return res.data.filter((x) => x.id !== l.id).slice(0, take)
        } catch {
          return [] // "similar" is a nice-to-have: never fail the main listing because of it
        }
      },
    },
  },
})
