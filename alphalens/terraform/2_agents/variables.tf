variable "aws_region" {
  description = "AWS region for Lambda and SQS"
  type        = string
  default     = "us-east-1"
}

variable "aurora_cluster_arn" {
  description = "Aurora cluster ARN from terraform/1_database"
  type        = string
}

variable "aurora_secret_arn" {
  description = "Secrets Manager ARN from terraform/1_database"
  type        = string
}

variable "database_name" {
  description = "Database name"
  type        = string
  default     = "alphalens"
}

variable "bedrock_model_id" {
  description = "Bedrock model ID for future LLM agents"
  type        = string
  default     = "us.amazon.nova-pro-v1:0"
}

variable "bedrock_region" {
  description = "Bedrock region (LiteLLM uses AWS_REGION_NAME)"
  type        = string
  default     = "us-west-2"
}

variable "llm_provider" {
  description = "LLM backend for zip Lambdas: bedrock or openai"
  type        = string
  default     = "bedrock"
}

variable "openai_api_key" {
  description = "OpenAI API key when llm_provider=openai"
  type        = string
  default     = ""
  sensitive   = true
}

variable "openai_model_id" {
  description = "OpenAI model when llm_provider=openai"
  type        = string
  default     = "gpt-4.1-mini"
}

variable "discovery_service_url" {
  description = "Live discovery Lambda URL from terraform/3_discovery (optional)"
  type        = string
  default     = ""
}

variable "use_llm_orchestration" {
  description = "Enable Bedrock LLM orchestrator on alphalens-orchestrator (package via backend/orchestrator/package_docker.py — Alex planner pattern)"
  type        = bool
  default     = false
}

variable "use_llm_portfolio" {
  description = "Enable LLM portfolio narrative on alphalens-portfolio (slim OpenAI/Bedrock — actions stay deterministic)"
  type        = bool
  default     = false
}

variable "use_llm_qa" {
  description = "Enable Bedrock LLM Q&A on alphalens-qa (package via backend/qa/package_docker.py — Alex planner pattern)"
  type        = bool
  default     = false
}

variable "use_llm_analyst_narrative" {
  description = "Enable LLM analyst narrative on alphalens-analyst (slim OpenAI/Bedrock — no litellm) and alphalens-orchestrator pipeline"
  type        = bool
  default     = false
}

variable "use_llm_validator_narrative" {
  description = "Enable LLM validator narrative on alphalens-validator (slim OpenAI/Bedrock — status stays deterministic)"
  type        = bool
  default     = false
}
