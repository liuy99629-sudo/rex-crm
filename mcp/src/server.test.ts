import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js'
import { beforeEach, describe, expect, it } from 'vitest'
import { RexApi, type Fetch } from './api.js'
import { createServer } from './server.js'

interface Call {
  method: string
  path: string
  query: Record<string, string>
  body: unknown
  auth: string | null
}

type Handler = (call: Call) => { status?: number; body: unknown }

/** Fake Rex CRM API: routes "METHOD /path" to handlers and records every request. */
function fakeApi(routes: Record<string, Handler>) {
  const calls: Call[] = []
  const fetchImpl: Fetch = async (input, init) => {
    const url = new URL(String(input))
    const path = url.pathname.replace(/^\/api/, '')
    const headers = new Headers(init?.headers)
    const call: Call = {
      method: init?.method ?? 'GET',
      path,
      query: Object.fromEntries(url.searchParams),
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
      auth: headers.get('Authorization'),
    }
    calls.push(call)
    const handler = routes[`${call.method} ${path}`]
    const res = handler ? handler(call) : { status: 404, body: { message: 'Not found.' } }
    return new Response(JSON.stringify(res.body), { status: res.status ?? 200 })
  }
  return { calls, api: new RexApi('http://crm.test/api/', 'tok-123', fetchImpl) }
}

async function connect(api: RexApi) {
  const [clientSide, serverSide] = InMemoryTransport.createLinkedPair()
  await createServer(api).connect(serverSide)
  const client = new Client({ name: 'test', version: '1.0.0' })
  await client.connect(clientSide)
  return client
}

const textOf = (r: Awaited<ReturnType<Client['callTool']>>) =>
  (r.content as { type: string; text: string }[]).map((c) => c.text).join('\n')

const deal = (stage: string, stage_label: string) => ({
  id: 7,
  title: 'Purchase - Smith',
  stage,
  stage_label,
  value: 950000,
  expected_close_date: '2026-12-01',
  closed_at: null,
  notes: null,
  contact: { id: 3, name: 'Jane Smith' },
  property: { id: 2, title: 'Family home', suburb: 'Burwood' },
  agent: { id: 1, name: 'Demo Agent' },
  activities: [{ id: 1, type: 'note', body: 'Called buyer', user: { id: 1, name: 'Demo Agent' }, created_at: '2026-11-10T10:00:00Z' }],
})

describe('Rex CRM MCP server', () => {
  let stage = 'offer'
  beforeEach(() => {
    stage = 'offer'
  })

  const routes: Record<string, Handler> = {
    'GET /contacts': () => ({
      body: {
        data: [
          { id: 3, name: 'Jane Smith', email: 'jane@example.com', phone: null, type: 'buyer', budget_min: 900000, budget_max: 1200000 },
        ],
        meta: { current_page: 1, last_page: 3, per_page: 25, total: 60 },
      },
    }),
    'GET /deals/7': () => ({ body: deal(stage, stage === 'offer' ? 'Offer' : 'Negotiation') }),
    'PATCH /deals/7/stage': (c) => {
      stage = (c.body as { stage: string }).stage
      return { body: deal(stage, 'Negotiation') }
    },
    'POST /contacts': () => ({ status: 422, body: { message: 'The email field must be a valid email address.', errors: { email: ['Invalid.'] } } }),
    'POST /ai/ask': () => ({ status: 503, body: { message: 'The AI assistant is not configured.' } }),
    'GET /dashboard': () => ({ status: 401, body: { message: 'Unauthenticated.' } }),
  }

  it('lists tools with read-only and write hints', async () => {
    const client = await connect(fakeApi(routes).api)
    const { tools } = await client.listTools()
    const byName = Object.fromEntries(tools.map((t) => [t.name, t]))

    expect(Object.keys(byName).sort()).toEqual(
      ['add_deal_note', 'ask_rex', 'create_contact', 'dashboard_stats', 'get_deal', 'get_pipeline', 'move_deal_stage', 'search_contacts', 'search_properties'].sort(),
    )
    expect(byName.search_contacts.annotations?.readOnlyHint).toBe(true)
    expect(byName.move_deal_stage.annotations?.readOnlyHint).toBe(false)
    expect(Object.keys(byName).some((n) => n.includes('delete'))).toBe(false)
  })

  it('searches contacts with the token and formats the result', async () => {
    const { api, calls } = fakeApi(routes)
    const client = await connect(api)

    const r = await client.callTool({ name: 'search_contacts', arguments: { query: 'smith', type: 'buyer' } })

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/contacts', query: { q: 'smith', type: 'buyer', per_page: '25' }, auth: 'Bearer tok-123' })
    expect(textOf(r)).toContain('Jane Smith (contact #3, buyer) · budget $900,000–$1,200,000 · jane@example.com')
    expect(textOf(r)).toContain('showing 1 of 60')
  })

  it('moves a deal through the API and reports from and to', async () => {
    const { api, calls } = fakeApi(routes)
    const client = await connect(api)

    const r = await client.callTool({ name: 'move_deal_stage', arguments: { deal_id: 7, stage: 'negotiation' } })

    expect(calls.map((c) => `${c.method} ${c.path}`)).toEqual(['GET /deals/7', 'PATCH /deals/7/stage'])
    expect(calls[1].body).toEqual({ stage: 'negotiation' })
    expect(textOf(r)).toBe('Moved Purchase - Smith (deal #7) from Offer to Negotiation.')
  })

  it('rejects invalid input before calling the API', async () => {
    const { api, calls } = fakeApi(routes)
    const client = await connect(api)

    const r = await client.callTool({ name: 'move_deal_stage', arguments: { deal_id: 7, stage: 'archived' } })

    expect(r.isError).toBe(true)
    expect(calls).toHaveLength(0)
  })

  it('returns validation errors as a readable tool error', async () => {
    const client = await connect(fakeApi(routes).api)

    const r = await client.callTool({ name: 'create_contact', arguments: { name: 'Bob', type: 'buyer', email: 'bob@example.com' } })

    expect(r.isError).toBe(true)
    expect(textOf(r)).toContain('- email: Invalid.')
  })

  it('explains an expired token', async () => {
    const r = await (await connect(fakeApi(routes).api)).callTool({ name: 'dashboard_stats', arguments: {} })

    expect(r.isError).toBe(true)
    expect(textOf(r)).toContain('npm run login')
  })

  it('falls back gracefully when the AI assistant is not configured', async () => {
    const r = await (await connect(fakeApi(routes).api)).callTool({ name: 'ask_rex', arguments: { question: 'Who wants a pool?' } })

    expect(r.isError).toBeFalsy()
    expect(textOf(r)).toContain('not available')
  })

  it('shows deal detail with recent activity', async () => {
    const r = await (await connect(fakeApi(routes).api)).callTool({ name: 'get_deal', arguments: { deal_id: 7 } })

    expect(textOf(r)).toContain('Stage: Offer · Value: $950,000')
    expect(textOf(r)).toContain('2026-11-10 Note: Called buyer (Demo Agent)')
  })
})
