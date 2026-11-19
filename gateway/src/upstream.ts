/** Calls the CRM's public REST endpoints (/api/public/*). No credentials: they are public by design. */

export type Fetch = typeof fetch

export interface ListingDto {
  id: number
  title: string
  address_line: string
  suburb: string
  state: string
  postcode: string
  type: string
  status: string
  price: number | null
  bedrooms: number | null
  bathrooms: number | null
  parking: number | null
  land_size_sqm: number | null
  description: string | null
  listed_at: string | null
  agent_name?: string | null
}

export interface Page<T> {
  data: T[]
  meta: { current_page: number; last_page: number; total: number }
}

export class UpstreamError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly errors: Record<string, string[]> = {},
  ) {
    super(message)
  }
}

export class CrmPublicApi {
  private readonly base: string

  constructor(
    baseUrl: string,
    /** The visitor's IP, forwarded so the CRM rate-limits per visitor rather than per gateway. */
    private readonly clientIp: string | null,
    private readonly fetchImpl: Fetch = fetch,
  ) {
    this.base = baseUrl.replace(/\/+$/, '')
  }

  private async request<T>(method: string, path: string, opts: { query?: Record<string, unknown>; body?: unknown } = {}): Promise<T> {
    const url = new URL(`${this.base}/public${path}`)
    for (const [k, v] of Object.entries(opts.query ?? {})) {
      if (v !== null && v !== undefined && v !== '') url.searchParams.set(k, String(v))
    }
    const headers: Record<string, string> = { Accept: 'application/json' }
    if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
    if (this.clientIp) headers['X-Forwarded-For'] = this.clientIp
    const res = await this.fetchImpl(url, { method, headers, body: opts.body === undefined ? undefined : JSON.stringify(opts.body) })
    const payload = (await res.json().catch(() => ({}))) as Record<string, unknown>
    if (!res.ok) {
      throw new UpstreamError(res.status, String(payload.message ?? `CRM returned ${res.status}`), (payload.errors as Record<string, string[]>) ?? {})
    }
    return payload as T
  }

  listings(query: Record<string, unknown>) {
    return this.request<Page<ListingDto>>('GET', '/listings', { query })
  }

  async listing(id: number): Promise<ListingDto | null> {
    try {
      return await this.request<ListingDto>('GET', `/listings/${id}`)
    } catch (err) {
      if (err instanceof UpstreamError && err.status === 404) return null
      throw err
    }
  }

  enquire(body: Record<string, unknown>) {
    return this.request<{ reference: string; message: string }>('POST', '/enquiries', { body })
  }
}
