# Rex CRM MCP server

Lets Claude (Claude Code, Claude Desktop or any MCP client) work with the CRM directly:
"Which buyers have a budget over $1.2m?", "Move the Smith deal to negotiation and note that finance is approved".

It is a TypeScript [Model Context Protocol](https://modelcontextprotocol.io) server over stdio. Every call
goes through the CRM's REST API with your own login, so validation, permissions, the dashboard cache
and queued jobs behave exactly as in the web app.

| Tool | What it does | Changes data |
|---|---|---|
| `search_contacts` | Find clients by name, email or phone and type | no |
| `search_properties` | Find listings by text, status, type and price range | no |
| `get_pipeline` | Deals by stage with totals | no |
| `get_deal` | One deal with contact, property and recent activity | no |
| `dashboard_stats` | Headline numbers | no |
| `ask_rex` | Ask the built-in AI assistant (semantic search over notes) | no |
| `move_deal_stage` | Change a deal's stage ("won" also marks the property sold) | yes |
| `add_deal_note` | Add a note to a deal | yes |
| `create_contact` | Add a client | yes |

There are no delete tools on purpose. The resource `rex://pipeline` gives the whole pipeline as context.
MCP clients ask you before running a tool (unless you allow it), and the write tools are marked as
non-read-only so clients can treat them differently.

## Set up

```bash
cd mcp
npm ci
npm run build
npm run login        # asks for your CRM email + password once, prints a token
```

Keep the token secret, like a password. Logging out of the web app does not revoke it.

### Claude Code (this repo)

The repo's `.mcp.json` registers the server as `rex-crm`. Set the token in your environment before
starting Claude Code in the repo root:

```powershell
$env:REX_API_TOKEN = "<token>"      # Windows PowerShell
```

```bash
export REX_API_TOKEN="<token>"      # macOS / Linux
```

`REX_API_URL` defaults to `http://localhost:8080/api` (the Docker stack); point it at another deployment if needed.

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rex-crm": {
      "command": "node",
      "args": ["C:/path/to/rex-crm/mcp/dist/index.js"],
      "env": { "REX_API_URL": "http://localhost:8080/api", "REX_API_TOKEN": "<token>" }
    }
  }
}
```

## Develop

```bash
npm test             # in-memory MCP client against a fake CRM API
npm run typecheck
```
