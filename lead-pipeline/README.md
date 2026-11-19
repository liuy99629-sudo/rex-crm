# Email lead pipeline (AWS)

Most real-estate leads arrive as **emails from the portals** (realestate.com.au, Domain) or directly from
buyers. This pipeline turns each one into a CRM lead automatically, so nobody has to copy leads out of an inbox.

```
enquiries@agency ──► SES receipt rule ──► S3 inbox/ ──(ObjectCreated)──► Lambda (Python)
                                                                      │  1. parse the email
                                                                      │  2. claim it in DynamoDB (idempotent)
                                                                      │  3. extract the lead with Claude in Amazon Bedrock
                                                                      │  4. POST /api/integrations/leads (limited token)
                                                                      ▼
                                       DynamoDB ledger (audit, 90-day TTL) · SQS dead-letter queue + CloudWatch alarm
```

## What happens to an email

| Outcome | When | Ledger status |
|---|---|---|
| New lead in the CRM | A person enquiring about a property | `processed` (with the CRM reference) |
| Skipped | Newsletter, receipt, spam, or no usable email address | `ignored` (with the reason) |
| Skipped | The same email delivered again (S3 and Lambda deliver at least once) | unchanged, reported as `duplicate` |
| Kept for a person to look at | The CRM rejected the data (422) | `rejected` |
| Retried, then dead-lettered | Bedrock or the CRM unavailable | `failed` (a retry may take it over) |

In the CRM, the lead goes through the same `LeadIntake` service as website enquiries:
- The contact is matched by email or created, with the portal recorded as the source.
- The listing is found from the address or title in the email, and the Lead deal is assigned to that listing's agent.
- The message becomes a note.
- A repeat enquiry adds a note to the open deal instead of creating another.

## Extraction

- **On AWS, Claude in Amazon Bedrock** (`bedrock-mantle` endpoint, `anthropic.claude-opus-5-5`).
  - IAM auth comes from the Lambda role; the only permission needed is `bedrock-mantle:CreateInference`.
  - It uses structured outputs, so the reply always matches `LEAD_SCHEMA`.
  - The prompt treats email content as data, not instructions.
  - Bedrock has no server-side refusal fallback, so the SDK's `BetaRefusalFallbackMiddleware` retries a refusal on `anthropic.claude-opus-4-8`.
- **Locally and in tests, `RuleExtractor`**: labelled fields ("Name:", "Email:", …). LocalStack has no Bedrock.

The email body (names, emails, phone numbers) is sent to Bedrock in your AWS account. Raw emails expire from S3 after 30 days.

## Deploy (AWS SAM)

1. Create the CRM token and store it in SSM:
   ```bash
   php artisan rex:integration-token lead-pipeline
   ```
   ```bash
   aws ssm put-parameter --name /rex-crm/lead-pipeline-token --type SecureString --value "<token>"
   ```
   The token can only call `POST /api/integrations/leads`; every other CRM route returns 403 for it.
2. Enable access to Claude Opus 5.5 in the Amazon Bedrock console (ap-southeast-2).
3. Deploy:
   ```bash
   sam build && sam deploy --parameter-overrides CrmApiUrl=https://crm.example.com/api
   ```
4. In SES, verify your domain and add a receipt rule for the enquiries address with an **S3 action** to the
   `InboundMailBucketName` output, object key prefix `inbox/`. The bucket policy already allows SES to write
   there. SES email receiving is offered in a limited set of regions: check that yours supports it.

CI/CD: on `main`, GitHub Actions deploys with OIDC once the repository variables `AWS_DEPLOY_ROLE_ARN` and
`CRM_PUBLIC_API_URL` are set. Every pull request runs the tests, `sam validate --lint` and `sam build`.

## Run locally (LocalStack)

```bash
docker compose exec api php artisan rex:integration-token lead-pipeline   # put it in .env as LEAD_PIPELINE_TOKEN
```

```bash
docker compose --profile aws up -d --build                                # LocalStack + runner; uploads samples/*.eml
```

```bash
docker compose logs -f lead-pipeline
```

The runner polls `inbox/` in the LocalStack bucket and calls the same `process_email` the Lambda does.

## Test

```bash
docker compose --profile test run --rm lead-pipeline-test   # moto (S3, DynamoDB, SSM) + fake CRM, no AWS account
```
