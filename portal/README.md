# Public listings portal

The agency's public website, where buyers search listings and send enquiries that land in the CRM as leads.

```
Browser ──► portal (Next.js, :3000) ──GraphQL──► gateway (Node, :4000) ──REST──► Laravel /api/public/*
              server-rendered pages              public schema, error codes       listings on the market,
              + Server Action for the form       visitor IP forwarded              enquiry → contact + lead + note
```

- **Portal (`portal/`)**: Next.js 16 App Router.
  - Search and listing pages render on the server: they are fast, SEO-friendly (per-listing `<title>` and description) and work without JavaScript.
  - The search form is a plain GET form, so every search has a shareable URL.
  - The enquiry form uses a Server Action, so the gateway is never exposed to the browser.
- **Gateway (`gateway/`)**: GraphQL Yoga on Node.
  - One typed public schema: `listings`, `listing { similar }` and `submitEnquiry`.
  - CRM errors map to stable codes (`BAD_USER_INPUT`, `NOT_FOUND`, `RATE_LIMITED`, `UPSTREAM_ERROR`). Anything else is masked.
  - GraphiQL is at http://localhost:4000/graphql in development.
- **Laravel** (`PublicListingController`, `PublicEnquiryController`):
  - Exposes only listings that are active or under offer, without vendor or internal fields.
  - An enquiry matches the contact by email (or creates one with source "Website"). It opens a Lead deal on the listing, assigned to the listing agent, and adds the message as a note. A repeat enquiry adds a note to the open deal instead of creating another.
  - Rate limits: 5 enquiries per minute per visitor (the IP is forwarded through the portal and gateway), plus a honeypot field.

## Run

`docker compose up --build -d`, then open http://localhost:3000.

## Test

```bash
cd gateway && npm ci && npm test     # GraphQL schema against a fake CRM
cd portal && npm ci && npm test      # search-param parsing and display helpers
cd backend && php artisan test --filter PublicPortalTest
```
