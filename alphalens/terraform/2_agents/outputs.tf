output "sqs_queue_url" {
  description = "SQS queue URL for analysis jobs"
  value       = aws_sqs_queue.analysis_jobs.url
}

output "sqs_queue_arn" {
  description = "SQS queue ARN for analysis jobs"
  value       = aws_sqs_queue.analysis_jobs.arn
}

output "deep_research_queue_url" {
  description = "SQS queue URL for Phase 2 async deep research"
  value       = aws_sqs_queue.deep_research_jobs.url
}

output "deep_research_queue_arn" {
  description = "SQS queue ARN for Phase 2 async deep research"
  value       = aws_sqs_queue.deep_research_jobs.arn
}

output "deep_research_trigger_function_name" {
  description = "Lambda that POSTs deep research jobs to discovery-live"
  value       = aws_lambda_function.deep_research_trigger.function_name
}

output "orchestrator_function_name" {
  description = "Orchestrator Lambda function name"
  value       = aws_lambda_function.orchestrator.function_name
}

output "lambda_agents_role_arn" {
  description = "IAM role ARN for agent Lambdas"
  value       = aws_iam_role.lambda_agents_role.arn
}

output "agent_function_names" {
  description = "All agent Lambda function names"
  value = {
    orchestrator = aws_lambda_function.orchestrator.function_name
    validator    = aws_lambda_function.validator.function_name
    analyst      = aws_lambda_function.analyst.function_name
    portfolio    = aws_lambda_function.portfolio.function_name
    discovery    = aws_lambda_function.discovery.function_name
    qa           = aws_lambda_function.qa.function_name
  }
}

output "setup_instructions" {
  description = "Post-deploy setup steps"
  value       = <<-EOT

    ✅ AlphaLens agent orchestra deployed!

    Add to alphalens/.env:
    SQS_QUEUE_URL=${aws_sqs_queue.analysis_jobs.url}
    ORCHESTRATOR_FUNCTION=${aws_lambda_function.orchestrator.function_name}
    QA_FUNCTION=${aws_lambda_function.qa.function_name}

    Tail orchestrator logs:
    aws logs tail /aws/lambda/alphalens-orchestrator --follow

    Enqueue a test job (after creating a row in analysis_jobs):
    aws sqs send-message --queue-url ${aws_sqs_queue.analysis_jobs.url} --message-body '{"jobId":"<uuid>"}'
  EOT
}
