#!/usr/bin/env node
/**
 * Get an API token for the MCP server: `npm run login`.
 * Asks for your CRM email and password in this terminal, signs in once, and prints a token
 * named "mcp" to put in REX_API_TOKEN. The password is not stored anywhere.
 */
import { createInterface } from 'node:readline/promises'
import { stdin, stdout } from 'node:process'

const url = (process.env.REX_API_URL ?? 'http://localhost:8080/api').replace(/\/+$/, '')
const rl = createInterface({ input: stdin, output: stdout })

const email = (await rl.question(`Rex CRM email (${url}): `)).trim()
const password = await rl.question('Password: ')
rl.close()

const res = await fetch(`${url}/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
  body: JSON.stringify({ email, password, device_name: 'mcp' }),
})
const body = (await res.json().catch(() => ({}))) as { token?: string; message?: string }

if (!res.ok || !body.token) {
  console.error(`Login failed: ${body.message ?? res.status}`)
  process.exit(1)
}

console.log('\nToken (keep it secret, like a password):\n')
console.log(body.token)
console.log('\nSet it as REX_API_TOKEN for the MCP server (see mcp/README.md).')
