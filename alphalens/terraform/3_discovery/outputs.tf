output "ecr_repository_url" {
  description = "ECR repository URL for discovery container images"
  value       = aws_ecr_repository.discovery.repository_url
}

output "discovery_service_url" {
  description = "Public HTTPS URL for live discovery (POST /discover)"
  value = try(
    nonsensitive(trimsuffix(aws_lambda_function_url.discovery[0].function_url, "/")),
    "Not deployed yet — run: cd alphalens/backend/discovery && uv run deploy.py"
  )
}

output "discovery_function_name" {
  description = "Lambda function name for live discovery"
  value       = try(nonsensitive(aws_lambda_function.discovery[0].function_name), "Not deployed yet")
}

output "setup_instructions" {
  description = "Post-deploy wiring steps"
  value = local.discovery_deployed ? format(
    "Live discovery deployed.\n\nService URL: %s\n\n1. Add to alphalens/.env:\n   DISCOVERY_SERVICE_URL=%s\n\n2. Re-apply terraform/2_agents with discovery_service_url set,\n   or update alphalens-orchestrator Lambda env DISCOVERY_SERVICE_URL.\n\n3. Test:\n   curl %s/health",
    nonsensitive(aws_lambda_function_url.discovery[0].function_url),
    nonsensitive(trimsuffix(aws_lambda_function_url.discovery[0].function_url, "/")),
    nonsensitive(trimsuffix(aws_lambda_function_url.discovery[0].function_url, "/"))
  ) : "Run 'cd alphalens/backend/discovery && uv run deploy.py' (Docker required)."
}
