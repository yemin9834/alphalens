# AlphaLens — Guide 1: Permissions

AlphaLens runs in the same AWS account as Alex. Start with the Alex IAM setup, then add any AlphaLens-specific permissions.

## Required: Alex base permissions

Complete [../../guides/1_permissions.md](../../guides/1_permissions.md) if you have not already:

- IAM user `aiengineer` in the `AlexAccess` group
- AWS CLI configured (`aws configure`)
- Core policies for Lambda, S3, API Gateway, etc.

Verify:

```bash
aws sts get-caller-identity
```

## Required for Guide 2 (Database)

Before deploying `terraform/1_database`, you need RDS and Data API permissions.

**If you completed Alex Guide 5:** you already have these — skip to Guide 2.

**Otherwise**, follow **Step 0** in [../../guides/5_database.md](../../guides/5_database.md):

1. Create custom policy `AlexRDSCustomPolicy` (RDS, EC2 describe, Secrets Manager, KMS)
2. Attach to `AlexAccess` group:
   - `AmazonRDSDataFullAccess`
   - `SecretsManagerReadWrite`
   - `AlexRDSCustomPolicy`

Verify:

```bash
aws rds describe-db-clusters
aws rds-data execute-statement --help
```

## Required for Guide 3 (Agents)

- `AWSLambda_FullAccess` (or scoped Lambda policies)
- `AmazonSQSFullAccess`
- S3 permissions for Lambda package bucket (created by Terraform)

**Bedrock (optional for Guide 3 MVP):** deterministic agents do not call Bedrock in production. Request access now if you plan Guide 4:

- `bedrock:InvokeModel` for Nova Pro — see [../../guides/6_agents.md](../../guides/6_agents.md)
- Request **Nova Pro** in Bedrock console (us-west-2 recommended)

```bash
aws bedrock list-foundation-models --region us-west-2
```

## Required for Guide 4 (Discovery, optional)

- ECR and Lambda container permissions (Guide 4 live discovery — same pattern as Alex Researcher)
- See [../../guides/4_researcher.md](../../guides/4_researcher.md) for patterns

## Required for Guide 5 (Frontend + API Lambda)

- API Lambda needs the same Aurora and SQS permissions as agents
- `lambda:InvokeFunction` on `alphalens-*` agent Lambdas (for async jobs and Q&A)
- See [../../guides/7_frontend.md](../../guides/7_frontend.md) for patterns

## External API keys (not IAM)

Add to `alphalens/.env` as you need them:

| Service | Variable |
|---------|----------|
| Brave Search | `BRAVE_API_KEY` |
| Tavily | `TAVILY_API_KEY` |
| Alpha Vantage | `ALPHA_VANTAGE_API_KEY` |
| FRED | `FRED_API_KEY` |
| Clerk (frontend) | `CLERK_JWKS_URL` |

## Next step

Continue to [2_database.md](./2_database.md) to deploy Aurora.
