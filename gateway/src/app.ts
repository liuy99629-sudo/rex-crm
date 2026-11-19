import { createYoga, maskError } from 'graphql-yoga'
import { PUBLIC_ERROR_CODES, schema, type Context } from './schema.js'
import { CrmPublicApi, type Fetch } from './upstream.js'

/** First address in X-Forwarded-For (set by the portal or the load balancer). */
export function clientIp(headers: Headers): string | null {
  const forwarded = headers.get('x-forwarded-for')
  return forwarded ? forwarded.split(',')[0].trim() || null : null
}

type ErrorLike = { message?: string; extensions?: { code?: unknown }; originalError?: unknown }

/** The deepest error that carries one of our public codes, if any. */
function publicError(error: unknown): ErrorLike | null {
  let e = error as ErrorLike | undefined
  while (e) {
    if (typeof e.extensions?.code === 'string' && PUBLIC_ERROR_CODES.has(e.extensions.code)) return e
    e = e.originalError as ErrorLike | undefined
  }
  return null
}

export function createGateway(crmUrl: string, fetchImpl: Fetch = fetch) {
  return createYoga<{}, Context>({
    schema,
    graphqlEndpoint: '/graphql',
    graphiql: process.env.NODE_ENV !== 'production',
    // A public API: errors we raise on purpose (with a public code) pass through; anything else
    // (bugs, upstream details) is masked. Checked by code, not instanceof, so it holds even when
    // two copies of the graphql package are loaded (e.g. in tests).
    maskedErrors: {
      maskError: (error, message, isDev) => {
        const known = publicError(error)
        return known ? (error as Error) : maskError(error, message, isDev)
      },
    },
    context: ({ request }) => ({ crm: new CrmPublicApi(crmUrl, clientIp(request.headers), fetchImpl) }),
  })
}
