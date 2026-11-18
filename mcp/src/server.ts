import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js'
import type { CallToolResult } from '@modelcontextprotocol/sdk/types.js'
import { z } from 'zod'
import { RexApiError, type RexApi } from './api.js'
import { contactLine, dealDetail, list, money, pipelineSummary, propertyLine, stats } from './format.js'

// Mirrors backend/app/Enums (keep in sync, like frontend/src/api/types.ts).
const CONTACT_TYPES = ['buyer', 'seller', 'investor', 'tenant', 'landlord'] as const
const PROPERTY_TYPES = ['house', 'apartment', 'townhouse', 'land', 'commercial'] as const
const PROPERTY_STATUSES = ['draft', 'active', 'under_offer', 'sold', 'withdrawn'] as const
const DEAL_STAGES = ['lead', 'contacted', 'inspection', 'offer', 'negotiation', 'won', 'lost'] as const

const READ = { readOnlyHint: true, openWorldHint: false } as const
const WRITE = { readOnlyHint: false, destructiveHint: false, openWorldHint: false } as const

const text = (t: string): CallToolResult => ({ content: [{ type: 'text', text: t }] })

/** API failures become tool errors the model can read and act on, not protocol errors. */
async function run(fn: () => Promise<string>): Promise<CallToolResult> {
  try {
    return text(await fn())
  } catch (err) {
    if (err instanceof RexApiError) {
      const fields = Object.entries(err.errors).map(([f, msgs]) => `- ${f}: ${msgs.join(' ')}`)
      const hint =
        err.status === 401
          ? ' The REX_API_TOKEN is missing, expired or revoked: create a new one with `npm run login`.'
          : err.status === 404
            ? ' Check the id.'
            : ''
      return { isError: true, content: [{ type: 'text', text: [`${err.message}${hint}`, ...fields].join('\n') }] }
    }
    return { isError: true, content: [{ type: 'text', text: `Could not reach Rex CRM: ${(err as Error).message}` }] }
  }
}

export function createServer(api: RexApi): McpServer {
  const server = new McpServer(
    { name: 'rex-crm', version: '0.1.0' },
    {
      instructions:
        'Rex CRM for a real-estate agency: contacts (clients), properties (listings) and deals (sales pipeline). ' +
        'Money is whole Australian dollars. Look records up before changing them, refer to them by name and #id, ' +
        'and confirm with the user before moving a deal to won or lost. Nothing here can delete data.',
    },
  )

  server.registerTool(
    'search_contacts',
    {
      title: 'Search contacts',
      description: 'Find clients by name, email or phone, optionally filtered by type. Returns budget and contact details.',
      inputSchema: {
        query: z.string().optional().describe('Part of a name, email or phone number'),
        type: z.enum(CONTACT_TYPES).optional(),
      },
      annotations: READ,
    },
    ({ query, type }) =>
      run(async () => {
        const r = await api.searchContacts({ q: query, type, per_page: 25 })
        return list(r.data, r.meta.total, 'contacts', contactLine)
      }),
  )

  server.registerTool(
    'search_properties',
    {
      title: 'Search listings',
      description: 'Find properties by title, address or suburb, with optional status, type and price range (AUD).',
      inputSchema: {
        query: z.string().optional().describe('Part of a title, street address or suburb'),
        status: z.enum(PROPERTY_STATUSES).optional(),
        type: z.enum(PROPERTY_TYPES).optional(),
        min_price: z.number().int().nonnegative().optional(),
        max_price: z.number().int().nonnegative().optional(),
      },
      annotations: READ,
    },
    ({ query, ...filters }) =>
      run(async () => {
        const r = await api.searchProperties({ q: query, ...filters, per_page: 25 })
        return list(r.data, r.meta.total, 'properties', propertyLine)
      }),
  )

  server.registerTool(
    'get_pipeline',
    {
      title: 'Sales pipeline',
      description: 'Deals grouped by stage with counts, total value and the most recently updated deals in each stage.',
      inputSchema: {},
      annotations: READ,
    },
    () => run(async () => pipelineSummary(await api.pipeline())),
  )

  server.registerTool(
    'get_deal',
    {
      title: 'Deal details',
      description: 'One deal with its contact, property, agent, value, stage and recent notes and stage changes.',
      inputSchema: { deal_id: z.number().int().positive() },
      annotations: READ,
    },
    ({ deal_id }) => run(async () => dealDetail(await api.getDeal(deal_id))),
  )

  server.registerTool(
    'dashboard_stats',
    {
      title: 'Dashboard numbers',
      description: 'Headline numbers: contacts, active listings, open pipeline and deals won this month.',
      inputSchema: {},
      annotations: READ,
    },
    () => run(async () => stats(await api.dashboard())),
  )

  server.registerTool(
    'ask_rex',
    {
      title: 'Ask the Rex assistant',
      description:
        "Ask the CRM's built-in AI assistant a question in plain English. It searches notes and descriptions by meaning " +
        '(e.g. "buyers who want a pool"), which the exact-match search tools cannot do.',
      inputSchema: { question: z.string().min(3).max(2000) },
      annotations: { ...READ, openWorldHint: true },
    },
    ({ question }) =>
      run(async () => {
        try {
          return (await api.askRex(question)).answer
        } catch (err) {
          if (err instanceof RexApiError && (err.status === 503 || err.status === 404)) {
            return `The Rex assistant is not available (${err.message}). Use the search tools instead.`
          }
          throw err
        }
      }),
  )

  server.registerTool(
    'move_deal_stage',
    {
      title: 'Move a deal to another stage',
      description:
        'Change a deal\'s pipeline stage. Moving to "won" also marks its property as sold; "won" and "lost" close the deal. ' +
        'The CRM records the change in the deal history.',
      inputSchema: { deal_id: z.number().int().positive(), stage: z.enum(DEAL_STAGES) },
      annotations: { ...WRITE, idempotentHint: true },
    },
    ({ deal_id, stage }) =>
      run(async () => {
        const before = await api.getDeal(deal_id)
        const after = await api.setDealStage(deal_id, stage)
        return before.stage === after.stage
          ? `${after.title} (deal #${after.id}) is already in ${after.stage_label}. Nothing changed.`
          : `Moved ${after.title} (deal #${after.id}) from ${before.stage_label} to ${after.stage_label}.`
      }),
  )

  server.registerTool(
    'add_deal_note',
    {
      title: 'Add a note to a deal',
      description: 'Append a note to a deal\'s activity history (e.g. a call summary or next step).',
      inputSchema: { deal_id: z.number().int().positive(), note: z.string().min(1).max(5000) },
      annotations: WRITE,
    },
    ({ deal_id, note }) =>
      run(async () => {
        await api.addDealNote(deal_id, note)
        return `Added the note to deal #${deal_id}.`
      }),
  )

  server.registerTool(
    'create_contact',
    {
      title: 'Create a contact',
      description: 'Add a new client. Search first to avoid duplicates. Budgets are whole AUD dollars.',
      inputSchema: {
        name: z.string().min(1).max(255),
        type: z.enum(CONTACT_TYPES),
        email: z.string().email().optional(),
        phone: z.string().max(50).optional(),
        source: z.string().max(100).optional().describe('Lead source, e.g. Domain, referral, open home'),
        budget_min: z.number().int().nonnegative().optional(),
        budget_max: z.number().int().nonnegative().optional(),
        notes: z.string().max(5000).optional(),
      },
      annotations: WRITE,
    },
    (input) =>
      run(async () => {
        const c = await api.createContact(input)
        return `Created ${c.name} (contact #${c.id}, ${c.type}${c.budget_max ? `, budget up to ${money(c.budget_max)}` : ''}).`
      }),
  )

  server.registerResource(
    'pipeline',
    'rex://pipeline',
    {
      title: 'Sales pipeline',
      description: 'Current deals by stage (same as the get_pipeline tool), for attaching as context.',
      mimeType: 'text/plain',
    },
    async (uri) => ({ contents: [{ uri: uri.href, mimeType: 'text/plain', text: pipelineSummary(await api.pipeline(), 50) }] }),
  )

  return server
}
