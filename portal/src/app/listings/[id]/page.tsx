import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { cache } from 'react'
import { ListingCardView } from '@/components/ListingCard'
import { gql } from '@/lib/gateway'
import { LISTING_QUERY, features, typeLabel, type ListingDetail } from '@/lib/listings'
import { EnquiryForm } from './EnquiryForm'

type Props = { params: Promise<{ id: string }> }

// One gateway call per request, shared by generateMetadata and the page.
const getListing = cache(async (id: string) => (await gql<{ listing: ListingDetail | null }>(LISTING_QUERY, { id })).listing)

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const listing = await getListing((await params).id)
  if (!listing) return { title: 'Listing not found' }
  return {
    title: `${listing.title}, ${listing.suburb}`,
    description: `${features(listing)} ${typeLabel(listing.type).toLowerCase()} in ${listing.suburb} ${listing.state}. ${listing.priceLabel}.`,
  }
}

export default async function ListingPage({ params }: Props) {
  const listing = await getListing((await params).id)
  if (!listing) notFound()

  return (
    <article className="listing">
      <div className="listing-main">
        <div className="hero" aria-hidden>
          {typeLabel(listing.type)}
        </div>
        {listing.status === 'UNDER_OFFER' && <span className="tag">Under offer</span>}
        <h1>{listing.title}</h1>
        <p className="muted">
          {listing.address}, {listing.suburb} {listing.state} {listing.postcode}
        </p>
        <p className="price big">{listing.priceLabel}</p>
        <ul className="facts">
          <li>{typeLabel(listing.type)}</li>
          {features(listing) && <li>{features(listing)}</li>}
          {listing.landSizeSqm && <li>{listing.landSizeSqm} m² land</li>}
        </ul>
        {listing.description && <p className="description">{listing.description}</p>}

        {listing.similar.length > 0 && (
          <section>
            <h2>Similar properties</h2>
            <div className="grid small">
              {listing.similar.map((s) => (
                <ListingCardView key={s.id} listing={s} />
              ))}
            </div>
          </section>
        )}
      </div>

      <aside className="enquiry">
        <h2>Enquire about this property</h2>
        {listing.agentName && <p className="muted">Listing agent: {listing.agentName}</p>}
        <EnquiryForm listingId={listing.id} />
      </aside>
    </article>
  )
}
