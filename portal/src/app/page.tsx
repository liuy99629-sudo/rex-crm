import Link from 'next/link'
import { ListingCardView } from '@/components/ListingCard'
import { gql } from '@/lib/gateway'
import { LISTINGS_QUERY, PROPERTY_TYPES, pageHref, parseSearch, typeLabel, type ListingCard } from '@/lib/listings'

interface Result {
  listings: { total: number; page: number; lastPage: number; items: ListingCard[] }
}

export default async function SearchPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams
  const { filter, page } = parseSearch(params)
  const { listings } = await gql<Result>(LISTINGS_QUERY, { filter, page })
  const value = (k: string) => (typeof params[k] === 'string' ? (params[k] as string) : '')

  return (
    <>
      {/* A plain GET form: works without JavaScript and every search has a shareable URL. */}
      <form className="search" action="/">
        <input name="q" defaultValue={value('q')} placeholder="Suburb, street or feature (e.g. pool)" aria-label="Search" />
        <select name="type" defaultValue={value('type').toUpperCase()} aria-label="Property type">
          <option value="">Any type</option>
          {PROPERTY_TYPES.map((t) => (
            <option key={t} value={t}>
              {typeLabel(t)}
            </option>
          ))}
        </select>
        <select name="max" defaultValue={value('max')} aria-label="Maximum price">
          <option value="">Any price</option>
          {[750_000, 1_000_000, 1_500_000, 2_000_000, 3_000_000].map((p) => (
            <option key={p} value={p}>
              Up to ${p.toLocaleString('en-AU')}
            </option>
          ))}
        </select>
        <select name="beds" defaultValue={value('beds')} aria-label="Minimum bedrooms">
          <option value="">Any beds</option>
          {[1, 2, 3, 4, 5].map((b) => (
            <option key={b} value={b}>
              {b}+ beds
            </option>
          ))}
        </select>
        <button type="submit">Search</button>
      </form>

      <p className="count">
        {listings.total} {listings.total === 1 ? 'property' : 'properties'} for sale
      </p>

      {listings.items.length === 0 ? (
        <p className="empty">
          No properties match. <Link href="/">Clear the search</Link>
        </p>
      ) : (
        <div className="grid">
          {listings.items.map((l) => (
            <ListingCardView key={l.id} listing={l} />
          ))}
        </div>
      )}

      {listings.lastPage > 1 && (
        <nav className="pager" aria-label="Pages">
          {page > 1 && <Link href={pageHref(params, page - 1)}>← Previous</Link>}
          <span>
            Page {listings.page} of {listings.lastPage}
          </span>
          {page < listings.lastPage && <Link href={pageHref(params, page + 1)}>Next →</Link>}
        </nav>
      )}
    </>
  )
}
