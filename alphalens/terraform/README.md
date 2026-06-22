# AlphaLens Terraform

Independent Terraform modules with **local state** per directory (same pattern as Alex).

## Modules

| Directory | Guide | Resources |
|-----------|-------|-----------|
| `1_database/` | guides/2_database.md | Aurora Serverless v2, Secrets Manager |
| `2_agents/` | guides/3_agents.md | Lambdas, SQS, IAM, S3 packages |
| `3_discovery/` | guides/4_discovery.md | App Runner, ECR (optional) |
| `4_frontend/` | guides/5_frontend.md | API Gateway, API Lambda, S3, CloudFront |

## Usage

```bash
cd alphalens/terraform/1_database
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

**Required:** configure `terraform.tfvars` in each directory before apply.

State files (`terraform.tfstate`) are gitignored.

## Outputs

Use `terraform output` in each module and copy values to `alphalens/.env`.

Parent reference: [../../terraform/README.md](../../terraform/README.md)
