import type { Metadata } from 'next'
import Link from 'next/link'
import type { ReactNode } from 'react'
import './globals.css'

export const metadata: Metadata = {
  title: { default: 'Rex Realty | Property for sale in Sydney', template: '%s | Rex Realty' },
  description: 'Houses, apartments and townhouses for sale across Sydney. Enquire directly with the listing agent.',
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-AU">
      <body>
        <header className="site-header">
          <Link href="/" className="logo">
            Rex Realty
          </Link>
          <span className="tagline">Sydney property for sale</span>
        </header>
        <main className="container">{children}</main>
        <footer className="site-footer">Demo site for Rex CRM. All listings and people are fictional.</footer>
      </body>
    </html>
  )
}
