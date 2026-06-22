output "frontend_bucket" {
  description = "S3 bucket for static Next.js build"
  value       = aws_s3_bucket.frontend.id
}

output "api_gateway_url" {
  description = "API Gateway URL (30s max — debugging only; production uses CloudFront → Lambda Function URL)"
  value       = try(aws_apigatewayv2_api.main[0].api_endpoint, "Not deployed — run backend/api/package_docker.py first")
}

output "api_function_url" {
  description = "API Lambda Function URL (no 30s cap — CloudFront /api/* origin)"
  value       = try(aws_lambda_function_url.api[0].function_url, "Not deployed — run backend/api/package_docker.py first")
}

output "cloudfront_url" {
  description = "CloudFront URL for frontend + /api/* proxy"
  value       = try("https://${aws_cloudfront_distribution.main[0].domain_name}", "Not deployed — run backend/api/package_docker.py first")
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution id (for cache invalidation after frontend upload)"
  value       = try(aws_cloudfront_distribution.main[0].id, "Not deployed")
}

output "api_lambda_name" {
  description = "API Lambda function name"
  value       = try(aws_lambda_function.api[0].function_name, "Not deployed")
}

output "setup_instructions" {
  description = "Post-deploy steps"
  value = local.api_deployed ? format(
    <<-EOT
    AlphaLens frontend infrastructure deployed.

    CloudFront: https://%s
    API Gateway: %s
    S3 bucket: %s

    1. Build and upload frontend:
       cd alphalens/frontend && npm run build
       aws s3 sync out/ s3://%s/ --delete

    2. Add to frontend/.env.local:
       NEXT_PUBLIC_API_URL=https://%s

    3. Re-run terraform apply after CloudFront exists if you need CORS updated on the API Lambda.

    4. After s3 sync, invalidate CloudFront: aws cloudfront create-invalidation --distribution-id <id> --paths "/*"

    5. Test:
       curl https://%s/api/health
       curl https://%s/api/ecosystem/discover -X POST -H "Content-Type: application/json" -d '{"coreCompany":"NVIDIA","coreTicker":"NVDA"}'
    EOT
    ,
    aws_cloudfront_distribution.main[0].domain_name,
    aws_apigatewayv2_api.main[0].api_endpoint,
    aws_s3_bucket.frontend.id,
    aws_s3_bucket.frontend.id,
    aws_cloudfront_distribution.main[0].domain_name,
    aws_apigatewayv2_api.main[0].api_endpoint,
    aws_cloudfront_distribution.main[0].domain_name,
  ) : <<-EOT
    S3 bucket created. API + CloudFront deploy after packaging the API:

    cd alphalens/backend/api
    uv run package_docker.py

    cd ../../terraform/4_frontend
    terraform apply
  EOT
}
