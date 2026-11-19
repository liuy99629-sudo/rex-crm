import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="empty">
      <h1>Property not found</h1>
      <p>It may have sold or been taken off the market.</p>
      <Link href="/">See properties for sale</Link>
    </div>
  )
}
