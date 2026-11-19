import Link from 'next/link'
import { features, typeLabel, type ListingCard } from '@/lib/listings'

export function ListingCardView({ listing: l }: { listing: ListingCard }) {
  return (
    <Link href={`/listings/${l.id}`} className="card">
      <div className="card-photo" aria-hidden>
        {typeLabel(l.type)}
      </div>
      <div className="card-body">
        {l.status === 'UNDER_OFFER' && <span className="tag">Under offer</span>}
        <h2>{l.title}</h2>
        <p className="muted">
          {l.suburb} {l.state}
        </p>
        <p className="muted">{features(l)}</p>
        <p className="price">{l.priceLabel}</p>
      </div>
    </Link>
  )
}
