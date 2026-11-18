#!/usr/bin/env node
/**
 * Rex CRM MCP server (stdio). Configure in Claude Code / Claude Desktop with:
 *   REX_API_URL   e.g. http://localhost:8080/api  (default)
 *   REX_API_TOKEN a Sanctum token from `npm run login`
 * stdout carries the MCP protocol: log only to stderr.
 */
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { RexApi } from './api.js'
import { createServer } from './server.js'

const url = process.env.REX_API_URL ?? 'http://localhost:8080/api'
const token = process.env.REX_API_TOKEN

if (!token) {
  console.error('rex-crm-mcp: REX_API_TOKEN is not set. Create one with `npm run login` (in the mcp/ folder).')
  process.exit(1)
}

const server = createServer(new RexApi(url, token))
await server.connect(new StdioServerTransport())
console.error(`rex-crm-mcp: connected, using ${url}`)
