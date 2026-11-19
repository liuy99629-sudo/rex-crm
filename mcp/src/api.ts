/**
 * Thin client for the Rex CRM REST API. All reads and writes go through Laravel, so validation,
 * cache flushing and queued jobs work exactly as they do for the web app.
 */

export type Fetch = typeof fetch

export class RexApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly errors: Record<string, string[]> = {},
  ) {
    super(message)
  }
}

export type DealStage = 'lead' | 'contacted' | 'inspection' | 'offer' | 'negotiation' | 'won' | 'lost'

export interface NamedRef {
  id: number
  name: string
}

export interface Contact {
  id: number
  name: string
  email: string | null
  phone: string | null
  type: string
  source: string | null
  budget_min: number | null
  budget_max: number | null
  notes: string | null
  agent?: NamedRef | null
  deals_count?: number
}

export interface Property {
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
  owner?: NamedRef | null
}

export interface DealActivity {
  id: number
  type: 'note' | 'stage_change'
  body: string | null
  user?: NamedRef | null
  created_at: string
}

export interface Deal {
  id: number
  title: string
  stage: DealStage
  stage_label: string
  value: number
  expected_close_date: string | null
  closed_at: string | null
  notes: string | null
  contact?: NamedRef | null
  property?: { id: number; title: string; suburb: string } | null
  agent?: NamedRef | null
  activities?: DealActivity[]
}

export interface PipelineColumn {
  stage: DealStage
  label: string
  count: number
  total_value: number
  deals: Deal[]
}

export interface DashboardStats {
  contacts: number
  active_listings: number
  open_deals: number
  pipeline_value: number
  won_this_month: number
  won_value_this_month: number
}

export interface Paginated<T> {
  data: T[]
  meta: { current_page: number; last_page: number; per_page: number; total: number }
}

export interface AiAnswer {
  answer: string
  tool_calls: { tool: string; input: Record<string, unknown>; error: boolean }[]
}

export interface ContactInput {
  name: string
  type: string
  email?: string | null
  phone?: string | null
  source?: string | null
  budget_min?: number | null
  budget_max?: number | null
  notes?: string | null
}

type Query = Record<string, string | number | null | undefined>

export class RexApi {
  private readonly baseUrl: string

  constructor(
    baseUrl: string,
    private readonly token: string,
    private readonly fetchImpl: Fetch = fetch,
  ) {
    this.baseUrl = baseUrl.replace(/\/+$/, '')
  }

  private async request<T>(method: string, path: string, opts: { query?: Query; body?: unknown } = {}): Promise<T> {
    const url = new URL(this.baseUrl + path)
    for (const [k, v] of Object.entries(opts.query ?? {})) {
      if (v !== null && v !== undefined && v !== '') url.searchParams.set(k, String(v))
    }
    const res = await this.fetchImpl(url, {
      method,
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${this.token}`,
        ...(opts.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    })
    const text = await res.text()
    const payload = text ? safeJson(text) : null
    if (!res.ok) {
      const p = (payload ?? {}) as { message?: string; errors?: Record<string, string[]> }
      throw new RexApiError(res.status, p.message ?? `Rex CRM API returned ${res.status}`, p.errors ?? {})
    }
    return payload as T
  }

  me = () => this.request<NamedRef & { email: string; role: string }>('GET', '/auth/me')
  dashboard = () => this.request<{ data: DashboardStats }>('GET', '/dashboard').then((r) => r.data)
  pipeline = () => this.request<{ data: PipelineColumn[] }>('GET', '/pipeline').then((r) => r.data)
  searchContacts = (query: Query) => this.request<Paginated<Contact>>('GET', '/contacts', { query })
  searchProperties = (query: Query) => this.request<Paginated<Property>>('GET', '/properties', { query })
  getDeal = (id: number) => this.request<Deal>('GET', `/deals/${id}`)
  setDealStage = (id: number, stage: DealStage) => this.request<Deal>('PATCH', `/deals/${id}/stage`, { body: { stage } })
  addDealNote = (id: number, body: string) => this.request<DealActivity>('POST', `/deals/${id}/notes`, { body: { body } })
  createContact = (body: ContactInput) => this.request<Contact>('POST', '/contacts', { body })
  askRex = (question: string) =>
    this.request<AiAnswer>('POST', '/ai/ask', { body: { messages: [{ role: 'user', content: question }] } })
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return { message: text.slice(0, 200) }
  }
}
