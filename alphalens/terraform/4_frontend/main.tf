terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.82.0"
    }
  }
}

variable "aws_region" {
  description = "AWS region for frontend and API"
  type        = string
  default     = "us-east-1"
}

variable "cors_origins" {
  description = "Additional CORS origins (CloudFront URL is added automatically)"
  type        = list(string)
  default     = ["http://localhost:3000"]
}

variable "clerk_jwks_url" {
  description = "Clerk JWKS URL for JWT validation in the API Lambda"
  type        = string
  default     = ""
}

variable "clerk_issuer" {
  description = "Clerk issuer URL (optional, kept for compatibility)"
  type        = string
  default     = ""
}

variable "use_llm_qa" {
  description = "Deprecated on API — Q&A LLM runs on alphalens-qa (terraform/2_agents use_llm_qa). Leave false."
  type        = bool
  default     = false
}

variable "llm_provider" {
  description = "bedrock or openai — must match terraform/2_agents when use_llm_qa is true"
  type        = string
  default     = "bedrock"
}

variable "bedrock_model_id" {
  description = "Bedrock model id when llm_provider is bedrock"
  type        = string
  default     = "us.amazon.nova-pro-v1:0"
}

variable "bedrock_region" {
  description = "Bedrock region when llm_provider is bedrock"
  type        = string
  default     = "us-west-2"
}

variable "openai_api_key" {
  description = "OpenAI API key when llm_provider is openai"
  type        = string
  default     = ""
  sensitive   = true
}

variable "openai_model_id" {
  description = "OpenAI model id when llm_provider is openai"
  type        = string
  default     = "gpt-4.1-mini"
}

variable "api_lambda_timeout" {
  description = "alphalens-api Lambda timeout in seconds (live discovery needs 300+)"
  type        = number
  default     = 300
}

variable "discovery_http_timeout" {
  description = "Seconds to wait on live discovery HTTP from alphalens-api"
  type        = number
  default     = 300
}

variable "public_app_url" {
  description = "Public CloudFront URL for CORS (e.g. https://dxxxx.cloudfront.net) — required for direct stream API calls from the static site"
  type        = string
  default     = ""
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

data "terraform_remote_state" "database" {
  backend = "local"
  config = {
    path = "../1_database/terraform.tfstate"
  }
}

data "terraform_remote_state" "agents" {
  backend = "local"
  config = {
    path = "../2_agents/terraform.tfstate"
  }
}

data "terraform_remote_state" "discovery" {
  backend = "local"
  config = {
    path = "../3_discovery/terraform.tfstate"
  }
}

locals {
  name_prefix = "alphalens"
  api_zip     = "${path.module}/../../backend/api/api_lambda.zip"
  api_deployed = fileexists(local.api_zip)

  aurora_cluster_arn = data.terraform_remote_state.database.outputs.aurora_cluster_arn
  aurora_secret_arn  = data.terraform_remote_state.database.outputs.aurora_secret_arn
  database_name      = data.terraform_remote_state.database.outputs.database_name
  sqs_queue_url      = data.terraform_remote_state.agents.outputs.sqs_queue_url
  sqs_queue_arn      = data.terraform_remote_state.agents.outputs.sqs_queue_arn
  deep_research_queue_url = try(
    data.terraform_remote_state.agents.outputs.deep_research_queue_url,
    ""
  )
  deep_research_queue_arn = try(
    data.terraform_remote_state.agents.outputs.deep_research_queue_arn,
    ""
  )
  discovery_service_url = try(
    data.terraform_remote_state.discovery.outputs.discovery_service_url,
    ""
  )
  cors_origins_effective = distinct(compact(concat(
    var.cors_origins,
    var.public_app_url != "" ? [var.public_app_url] : [],
  )))
  common_tags = {
    Project   = "alphalens"
    Part      = "4_frontend"
    ManagedBy = "terraform"
  }

  agent_functions = [
    "alphalens-orchestrator",
    "alphalens-discovery",
    "alphalens-validator",
    "alphalens-analyst",
    "alphalens-portfolio",
    "alphalens-qa",
  ]

  # CloudFront * does not match /. One pattern per depth under /api/.
  # Deepest first (first match wins). Max: /api/jobs/{id}/ask/stream (4 segments).
  api_path_patterns = [
    "/api/*/*/*/*",
    "/api/*/*/*",
    "/api/*/*",
    "/api/*",
  ]

  # Shared with terraform/2_agents — required when api_lambda.zip exceeds ~70MB
  lambda_packages_bucket = "alphalens-lambda-packages-${data.aws_caller_identity.current.account_id}"

  # AWS Lambda Web Adapter — enables FastAPI StreamingResponse on Function URL (Mangum buffers SSE).
  lambda_adapter_layer_x86 = "arn:aws:lambda:${var.aws_region}:753240598075:layer:LambdaAdapterLayerX86:27"
}

# ---------------------------------------------------------------------------
# S3 static frontend
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "frontend" {
  bucket = "${local.name_prefix}-frontend-${data.aws_caller_identity.current.account_id}"
  tags   = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "404.html"
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.frontend.arn}/*"
      },
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.frontend]
}

# ---------------------------------------------------------------------------
# API Lambda (requires backend/api/api_lambda.zip from package_docker.py)
# ---------------------------------------------------------------------------

resource "aws_iam_role" "api_lambda_role" {
  count = local.api_deployed ? 1 : 0
  name  = "${local.name_prefix}-api-lambda-role"
  tags  = local.common_tags

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "api_lambda_basic" {
  count      = local.api_deployed ? 1 : 0
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.api_lambda_role[0].name
}

resource "aws_iam_role_policy" "api_lambda_aurora" {
  count = local.api_deployed ? 1 : 0
  name  = "${local.name_prefix}-api-lambda-aurora"
  role  = aws_iam_role.api_lambda_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "rds-data:ExecuteStatement",
          "rds-data:BatchExecuteStatement",
          "rds-data:BeginTransaction",
          "rds-data:CommitTransaction",
          "rds-data:RollbackTransaction"
        ]
        Resource = local.aurora_cluster_arn
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = local.aurora_secret_arn
      }
    ]
  })
}

resource "aws_iam_role_policy" "api_lambda_sqs" {
  count = local.api_deployed ? 1 : 0
  name  = "${local.name_prefix}-api-lambda-sqs"
  role  = aws_iam_role.api_lambda_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage", "sqs:GetQueueAttributes"]
        Resource = compact([local.sqs_queue_arn, local.deep_research_queue_arn])
      }
    ]
  })
}

resource "aws_iam_role_policy" "api_lambda_invoke" {
  count = local.api_deployed ? 1 : 0
  name  = "${local.name_prefix}-api-lambda-invoke"
  role  = aws_iam_role.api_lambda_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = [for fn in local.agent_functions : "arn:aws:lambda:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:function:${fn}"]
      }
    ]
  })
}

resource "aws_iam_role_policy" "api_lambda_bedrock" {
  count = local.api_deployed && var.use_llm_qa && var.llm_provider == "bedrock" ? 1 : 0
  name  = "${local.name_prefix}-api-lambda-bedrock"
  role  = aws_iam_role.api_lambda_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/*",
          "arn:aws:bedrock:*:*:inference-profile/*"
        ]
      }
    ]
  })
}

resource "aws_s3_object" "api_lambda_package" {
  count  = local.api_deployed ? 1 : 0
  bucket = local.lambda_packages_bucket
  key    = "api/api_lambda.zip"
  source = local.api_zip
  etag   = filemd5(local.api_zip)

  tags = local.common_tags
}

resource "aws_lambda_function" "api" {
  count            = local.api_deployed ? 1 : 0
  s3_bucket        = local.lambda_packages_bucket
  s3_key           = aws_s3_object.api_lambda_package[0].key
  function_name    = "${local.name_prefix}-api"
  role             = aws_iam_role.api_lambda_role[0].arn
  handler          = "run.sh"
  layers           = [local.lambda_adapter_layer_x86]
  source_code_hash = fileexists(local.api_zip) ? filebase64sha256(local.api_zip) : null
  runtime          = "python3.12"
  architectures    = ["x86_64"]
  timeout          = var.api_lambda_timeout
  memory_size      = 512
  tags             = local.common_tags

  environment {
    variables = {
      AURORA_CLUSTER_ARN    = local.aurora_cluster_arn
      AURORA_SECRET_ARN     = local.aurora_secret_arn
      DATABASE_NAME         = local.database_name
      DEFAULT_AWS_REGION    = var.aws_region
      SQS_QUEUE_URL              = local.sqs_queue_url
      DEEP_RESEARCH_QUEUE_URL    = local.deep_research_queue_url
      MOCK_LAMBDAS          = "false"
      DISCOVERY_FUNCTION    = "alphalens-discovery"
      VALIDATOR_FUNCTION    = "alphalens-validator"
      ANALYST_FUNCTION      = "alphalens-analyst"
      PORTFOLIO_FUNCTION    = "alphalens-portfolio"
      QA_FUNCTION           = "alphalens-qa"
      QA_STREAM_HEARTBEAT_SEC = "8"
      QA_STREAM_DELAY_MS      = "40"
      DISCOVERY_SERVICE_URL = local.discovery_service_url
      CLERK_JWKS_URL        = var.clerk_jwks_url
      CLERK_ISSUER          = var.clerk_issuer
      CORS_ORIGINS          = join(",", local.cors_origins_effective)
      DISCOVERY_HTTP_TIMEOUT         = tostring(var.discovery_http_timeout)
      DISCOVERY_STREAM_HTTP_TIMEOUT  = tostring(var.discovery_http_timeout)
      DISCOVERY_STREAM_HEARTBEAT_SEC = "8"
      AWS_LAMBDA_EXEC_WRAPPER        = "/opt/bootstrap"
      AWS_LWA_INVOKE_MODE            = "response_stream"
      PORT                           = "8000"
    }
  }

  depends_on = [
    aws_iam_role_policy.api_lambda_aurora,
    aws_iam_role_policy.api_lambda_sqs,
    aws_iam_role_policy.api_lambda_invoke,
    aws_iam_role_policy.api_lambda_bedrock,
    aws_s3_object.api_lambda_package,
  ]
}

# ---------------------------------------------------------------------------
# API Gateway HTTP API
# ---------------------------------------------------------------------------

resource "aws_apigatewayv2_api" "main" {
  count         = local.api_deployed ? 1 : 0
  name          = "${local.name_prefix}-api-gateway"
  protocol_type = "HTTP"
  tags          = local.common_tags

  cors_configuration {
    allow_credentials = false
    allow_headers     = ["authorization", "content-type", "x-amz-date", "x-api-key", "x-amz-security-token"]
    allow_methods     = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_origins     = ["*"]
    max_age           = 300
  }
}

resource "aws_apigatewayv2_stage" "default" {
  count       = local.api_deployed ? 1 : 0
  api_id      = aws_apigatewayv2_api.main[0].id
  name        = "$default"
  auto_deploy = true
  tags        = local.common_tags
}

resource "aws_apigatewayv2_integration" "lambda" {
  count                  = local.api_deployed ? 1 : 0
  api_id                 = aws_apigatewayv2_api.main[0].id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api[0].invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 30000
}

resource "aws_apigatewayv2_route" "api_any" {
  count     = local.api_deployed ? 1 : 0
  api_id    = aws_apigatewayv2_api.main[0].id
  route_key = "ANY /api/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda[0].id}"
}

resource "aws_apigatewayv2_route" "api_options" {
  count     = local.api_deployed ? 1 : 0
  api_id    = aws_apigatewayv2_api.main[0].id
  route_key = "OPTIONS /api/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda[0].id}"
}

resource "aws_apigatewayv2_route" "health" {
  count     = local.api_deployed ? 1 : 0
  api_id    = aws_apigatewayv2_api.main[0].id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.lambda[0].id}"
}

resource "aws_lambda_permission" "api_gw" {
  count         = local.api_deployed ? 1 : 0
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api[0].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main[0].execution_arn}/*/*"
}

# Lambda Function URL — no 30s API Gateway cap (CloudFront /api/* uses this origin).
# HTTP API v2 integration timeout is fixed at 30s and cannot be increased.
resource "aws_lambda_function_url" "api" {
  count              = local.api_deployed ? 1 : 0
  function_name      = aws_lambda_function.api[0].function_name
  authorization_type = "NONE"
  invoke_mode        = "RESPONSE_STREAM"
  # CORS is handled by FastAPI only — Function URL cors adds a second
  # Access-Control-Allow-Origin header and browsers reject the response.
}

resource "aws_lambda_permission" "api_function_url" {
  count                    = local.api_deployed ? 1 : 0
  statement_id             = "AllowPublicFunctionUrlInvoke"
  action                   = "lambda:InvokeFunctionUrl"
  function_name            = aws_lambda_function.api[0].function_name
  principal                = "*"
  function_url_auth_type   = "NONE"
}

# ---------------------------------------------------------------------------
# CloudFront — S3 for static files, Lambda Function URL for /api/*
# ---------------------------------------------------------------------------

# Next.js static export emits dashboard.html, not dashboard/index.html.
# Without this rewrite, /dashboard 404s on S3 and the custom error response serves index.html (Home).
resource "aws_cloudfront_function" "spa_html_routes" {
  count   = local.api_deployed ? 1 : 0
  name    = "${local.name_prefix}-spa-html-routes"
  runtime = "cloudfront-js-2.0"
  comment = "Rewrite /dashboard -> /dashboard.html for Next.js static export"
  publish = true
  code    = <<-EOF
function handler(event) {
  var request = event.request;
  var uri = request.uri;

  if (uri.startsWith("/_next")) {
    return request;
  }

  if (uri.endsWith("/")) {
    request.uri = uri + "index.html";
  } else if (!uri.includes(".")) {
    if (uri === "" || uri === "/") {
      request.uri = "/index.html";
    } else {
      request.uri = uri + ".html";
    }
  }

  return request;
}
EOF
}

resource "aws_cloudfront_distribution" "main" {
  count               = local.api_deployed ? 1 : 0
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  tags                = local.common_tags
  comment             = "AlphaLens frontend + API"

  origin {
    domain_name = aws_s3_bucket_website_configuration.frontend.website_endpoint
    origin_id   = "S3-${aws_s3_bucket.frontend.id}"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  origin {
    domain_name = trimprefix(trimsuffix(aws_lambda_function_url.api[0].function_url, "/"), "https://")
    origin_id   = "API-Lambda-URL"

    custom_origin_config {
      http_port                = 80
      https_port               = 443
      origin_protocol_policy   = "https-only"
      origin_ssl_protocols     = ["TLSv1.2"]
      origin_read_timeout      = 60
      origin_keepalive_timeout = 60
    }
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.frontend.id}"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa_html_routes[0].arn
    }
  }

  dynamic "ordered_cache_behavior" {
    for_each = local.api_path_patterns
    content {
      path_pattern     = ordered_cache_behavior.value
      allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
      cached_methods   = ["GET", "HEAD"]
      target_origin_id = "API-Lambda-URL"

      forwarded_values {
        query_string = true
        headers      = ["Authorization", "Content-Type", "Accept", "Origin"]
        cookies {
          forward = "all"
        }
      }

      viewer_protocol_policy = "redirect-to-https"
      min_ttl                = 0
      default_ttl            = 0
      max_ttl                = 0
    }
  }

  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  # Do not map 403 → index.html: authenticated /api/* routes return 403 JSON from
  # Lambda when Clerk rejects a request; replacing that body breaks the frontend.

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}
