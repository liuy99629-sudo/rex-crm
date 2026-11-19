import 'server-only'

/** Server-side GraphQL client for the public gateway. Never runs in the browser. */

const GATEWAY_URL = process.env.GATEWAY_URL ?? 'http://localhost:4000/graphql'

export class GatewayError extends Error {
  constructor(
    message: string,
    readonly code: string | null,
    readonly fields: Record<string, string[]> = {},
  ) {
    super(message)
  }
}

export async function gql<T>(
  query: string,
  variables: Record<string, unknown> = {},
  opts: { clientIp?: string | null; revalidate?: number | false } = {},
): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (opts.clientIp) headers['X-Forwarded-For'] = opts.clientIp
  const res = await fetch(GATEWAY_URL, {
    method: 'POST',
    headers,
    body: JSON.stringify({ query, variables }),
    // Listings change rarely: cache reads briefly; mutations pass revalidate: false.
    ...(opts.revalidate === false ? { cache: 'no-store' as const } : { next: { revalidate: opts.revalidate ?? 30 } }),
  })
  const body = (await res.json().catch(() => ({}))) as {
    data?: T
    errors?: { message: string; extensions?: { code?: string; fields?: Record<string, string[]> } }[]
  }
  if (body.errors?.length) {
    const e = body.errors[0]
    throw new GatewayError(e.message, e.extensions?.code ?? null, e.extensions?.fields ?? {})
  }
  if (!body.data) throw new GatewayError(`Gateway returned ${res.status}`, null)
  return body.data
}
