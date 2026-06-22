output "aurora_cluster_arn" {
  description = "ARN of the Aurora cluster"
  value       = aws_rds_cluster.aurora.arn
}

output "aurora_cluster_endpoint" {
  description = "Writer endpoint for the Aurora cluster"
  value       = aws_rds_cluster.aurora.endpoint
}

output "aurora_cluster_identifier" {
  description = "Cluster identifier"
  value       = aws_rds_cluster.aurora.cluster_identifier
}

output "aurora_secret_arn" {
  description = "ARN of the Secrets Manager secret containing database credentials"
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "database_name" {
  description = "Name of the database"
  value       = aws_rds_cluster.aurora.database_name
}

output "master_username" {
  description = "Master database username"
  value       = var.master_username
  sensitive   = true
}

output "lambda_role_arn" {
  description = "ARN of the IAM role for Lambda functions to access Aurora via Data API"
  value       = aws_iam_role.lambda_aurora_role.arn
}

output "lambda_role_name" {
  description = "Name of the IAM role for Lambda functions"
  value       = aws_iam_role.lambda_aurora_role.name
}

output "data_api_enabled" {
  description = "Whether the RDS Data API HTTP endpoint is enabled"
  value       = aws_rds_cluster.aurora.enable_http_endpoint ? "Enabled" : "Disabled"
}

output "setup_instructions" {
  description = "Post-deploy setup steps"
  value       = <<-EOT

    ✅ AlphaLens Aurora Serverless v2 cluster deployed successfully!

    Database Details:
    - Cluster: ${aws_rds_cluster.aurora.cluster_identifier}
    - Database: ${aws_rds_cluster.aurora.database_name}
    - Data API: Enabled
    - Region: ${var.aws_region}

    Add the following to alphalens/.env:
    AURORA_CLUSTER_ARN=${aws_rds_cluster.aurora.arn}
    AURORA_SECRET_ARN=${aws_secretsmanager_secret.db_credentials.arn}
    DATABASE_NAME=${aws_rds_cluster.aurora.database_name}
    DEFAULT_AWS_REGION=${var.aws_region}

    Test the Data API connection:
    aws rds-data execute-statement \
      --resource-arn ${aws_rds_cluster.aurora.arn} \
      --secret-arn ${aws_secretsmanager_secret.db_credentials.arn} \
      --database ${aws_rds_cluster.aurora.database_name} \
      --region ${var.aws_region} \
      --sql "SELECT version()"

    Set up the database schema (once migrations are implemented):
    cd alphalens/backend/database
    uv run run_migrations.py

    💰 Cost Management:
    - Current scaling: ${var.min_capacity} - ${var.max_capacity} ACUs
    - Estimated minimum: ~$43/month at 0.5 ACU
    - Destroy when not in use: cd alphalens/terraform/1_database && terraform destroy
  EOT
}
