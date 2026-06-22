variable "aws_region" {
  description = "AWS region for Lambda and ECR"
  type        = string
  default     = "us-east-1"
}

variable "discovery_image_uri" {
  description = "Full ECR image URI (set by deploy.py via discovery.auto.tfvars.json)"
  type        = string
  default     = ""
}

variable "bedrock_region" {
  description = "Bedrock region (LiteLLM uses AWS_REGION_NAME)"
  type        = string
  default     = "us-west-2"
}

variable "bedrock_model_id" {
  description = "Bedrock model ID when LLM_PROVIDER=bedrock"
  type        = string
  default     = "us.amazon.nova-pro-v1:0"
}

variable "llm_provider" {
  description = "bedrock or openai"
  type        = string
  default     = "bedrock"
}

variable "openai_api_key" {
  description = "OpenAI API key when LLM_PROVIDER=openai"
  type        = string
  default     = ""
  sensitive   = true
}

variable "openai_model_id" {
  description = "OpenAI model when LLM_PROVIDER=openai"
  type        = string
  default     = "gpt-4.1-mini"
}

variable "brave_api_key" {
  description = "Brave Search API key for discovery MCP"
  type        = string
  default     = ""
  sensitive   = true
}

variable "discovery_max_turns" {
  description = "Max agent turns per discovery run"
  type        = number
  default     = 10
}

variable "discovery_mcp_timeout" {
  description = "MCP session timeout in seconds"
  type        = number
  default     = 120
}

variable "discovery_playwright_mcp" {
  description = "Enable Playwright browser MCP (true/false string)"
  type        = string
  default     = "true"
}

variable "mcp_logging" {
  description = "Set to true for verbose MCP tool logging"
  type        = string
  default     = "false"
}

variable "aurora_cluster_arn" {
  description = "Aurora cluster ARN from terraform/1_database (optional — enables discovery persistence)"
  type        = string
  default     = ""
}

variable "aurora_secret_arn" {
  description = "Aurora secret ARN from terraform/1_database (optional)"
  type        = string
  default     = ""
}

variable "database_name" {
  description = "Database name"
  type        = string
  default     = "alphalens"
}

variable "persist_discovery_runs" {
  description = "Persist live discovery results to discovery_runs / candidates"
  type        = string
  default     = "true"
}

variable "deep_research_enabled" {
  description = "Run Phase 1 deep research after discovery candidates"
  type        = string
  default     = "true"
}

variable "deep_research_max_candidates" {
  description = "Max candidates to deep-research per discovery run"
  type        = number
  default     = 5
}

variable "deep_research_mode" {
  description = "inline (Phase 1 stream) or async (Phase 2 SQS worker)"
  type        = string
  default     = "async"
}

variable "deep_research_queue_url" {
  description = "SQS queue URL from terraform/2_agents deep_research_queue_url output"
  type        = string
  default     = ""
}

variable "deep_research_queue_arn" {
  description = "Optional override — defaults to ARN derived from deep_research_queue_url"
  type        = string
  default     = ""
}
