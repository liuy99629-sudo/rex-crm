# AI-first development workflow

The bottom half of the architecture diagram: **AI agents are the primary developers; engineers decompose, review and accept.**

```
Git repo --(task / code)--> AI coding agent --(open PR)--> CI build --(push image)--> Image registry --(deploy)--> GKE
```

| Step | In this repo |
|------|--------------|
| Task | A GitHub issue created from `.github/ISSUE_TEMPLATE/ai-task.md` (goal, context, acceptance criteria, out of scope) |
| AI coding agent | Claude (Claude Code in VS Code or the CLI) reads `CLAUDE.md`, works on a branch, runs the tests locally, opens a PR using `.github/PULL_REQUEST_TEMPLATE.md` |
| CI build | `.github/workflows/ci.yml`: backend tests, frontend tests + build on every PR |
| Image registry | On merge to `main`, API and web images are pushed to Google Artifact Registry, tagged with the commit SHA |
| Deploy | The same workflow applies `k8s/` to GKE with the new image tags and waits for rollouts |

## The human role

Because the agent writes most of the code, the engineer's leverage is in three places:

1. **Task breakdown**: small tasks with testable acceptance criteria. "Add a `lost_reason` to deals and show it on the card" is good; "improve the pipeline" is not.
2. **Review**: read the diff for behaviour, security and migration safety. CI only proves the tests pass.
3. **Acceptance**: run the preview (`docker compose up --build`) and check the feature does what the issue asked.

## Tips for good agent output

- Keep `CLAUDE.md` current: when you correct the agent twice about the same thing, write the rule down there.
- Ask for tests first on bug fixes (reproduce, then fix).
- One concern per PR. Large PRs get skimmed.
- Optional: add the `anthropics/claude-code-action` GitHub Action so `@claude` on an issue triggers an agent run automatically. It needs an `ANTHROPIC_API_KEY` repository secret.

## One-time GCP setup (for the deploy job)

```bash
PROJECT_ID=your-project; REGION=australia-southeast1

gcloud services enable container.googleapis.com artifactregistry.googleapis.com iamcredentials.googleapis.com
gcloud artifacts repositories create rex-crm --repository-format=docker --location=$REGION
gcloud container clusters create-auto rex-crm --region=$REGION     # GKE Autopilot
gcloud compute addresses create rex-crm-ip --global                 # for the Ingress

# Service account used by GitHub Actions
gcloud iam service-accounts create github-deployer
for role in artifactregistry.writer container.developer; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:github-deployer@$PROJECT_ID.iam.gserviceaccount.com" --role="roles/$role"
done
# Then create a Workload Identity Pool + GitHub provider and allow this repo to impersonate the account:
# https://github.com/google-github-actions/auth#preferred-direct-workload-identity-federation
```

GitHub repository settings:

- Variables: `GCP_PROJECT_ID`, `GCP_REGION`, `GAR_REPOSITORY` (`rex-crm`), `GKE_CLUSTER` (`rex-crm`), `GKE_LOCATION` (the region)
- Secrets: `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`
- Environment: `production` (add required reviewers if you want a manual approval before deploys)

In the cluster, create the app secret once (see `k8s/secret.example.yaml`):

```bash
gcloud container clusters get-credentials rex-crm --region=$REGION
kubectl apply -f k8s/namespace.yaml
kubectl -n rex-crm create secret generic rex-crm-secrets \
  --from-literal=APP_KEY="base64:$(openssl rand -base64 32)" \
  --from-literal=DB_PASSWORD="$(openssl rand -hex 16)"
```
