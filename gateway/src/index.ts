import { createServer } from 'node:http'
import { createGateway } from './app.js'

const crmUrl = process.env.CRM_API_URL ?? 'http://localhost:8000/api'
const port = Number(process.env.PORT ?? 4000)

const gateway = createGateway(crmUrl)
createServer(gateway).listen(port, () => {
  console.log(`rex-crm-gateway: GraphQL on http://localhost:${port}/graphql (CRM ${crmUrl})`)
})
