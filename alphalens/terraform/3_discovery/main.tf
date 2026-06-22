terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.28.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

locals {
  discovery_deployed   = var.discovery_image_uri != ""
  discovery_persistence = var.aurora_cluster_arn != "" && var.aurora_secret_arn != ""
  deep_research_sqs_parts = var.deep_research_queue_url != "" ? regex("^https://sqs\\.([^.]+)\\.amazonaws\\.com/([0-9]+)/(.+)$", var.deep_research_queue_url) : []
  deep_research_queue_arn = var.deep_research_queue_arn != "" ? var.deep_research_queue_arn : (
    length(local.deep_research_sqs_parts) == 3 ? "arn:aws:sqs:${local.deep_research_sqs_parts[0]}:${local.deep_research_sqs_parts[1]}:${local.deep_research_sqs_parts[2]}" : ""
  )
}

resource "aws_ecr_repository" "discovery" {
  name                 = "alphalens-discovery-live"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = false
  }

  tags = {
    Project = "alphalens"
    Part    = "3_discovery"
  }
}

resource "aws_ecr_repository_policy" "discovery_lambda_access" {
  repository = aws_ecr_repository.discovery.name

  policy = jsonencode({
    Version = "2008-10-17"
    Statement = [
      {
        Sid    = "LambdaEcrImageRetrievalPolicy"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
        Condition = {
          ArnLike = {
            "aws:sourceArn" = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:*"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role" "discovery_lambda_role" {
  name = "alphalens-discovery-live-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Project = "alphalens"
    Part    = "3_discovery"
  }
}

resource "aws_iam_role_policy_attachment" "discovery_lambda_basic" {
  role       = aws_iam_role.discovery_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "discovery_lambda_aurora_access" {
  count = local.discovery_persistence ? 1 : 0
  name  = "alphalens-discovery-live-aurora-policy"
  role  = aws_iam_role.discovery_lambda_role.id

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
        Resource = var.aurora_cluster_arn
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = var.aurora_secret_arn
      }
    ]
  })
}

resource "aws_iam_role_policy" "discovery_lambda_bedrock_access" {
  name = "alphalens-discovery-live-bedrock-policy"
  role = aws_iam_role.discovery_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:ListFoundationModels"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy" "discovery_lambda_sqs_send" {
  count = local.deep_research_queue_arn != "" ? 1 : 0
  name  = "alphalens-discovery-live-sqs-send"
  role  = aws_iam_role.discovery_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = local.deep_research_queue_arn
      }
    ]
  })
}

resource "aws_lambda_function" "discovery" {
  count         = local.discovery_deployed ? 1 : 0
  function_name = "alphalens-discovery-live"
  package_type  = "Image"
  image_uri     = var.discovery_image_uri
  role          = aws_iam_role.discovery_lambda_role.arn
  timeout       = 300
  memory_size   = 2048
  architectures = ["x86_64"]

  ephemeral_storage {
    size = 2048
  }

  environment {
    variables = {
      USE_LIVE_DISCOVERY       = "true"
      DISCOVERY_MCP_CONFIGURED = "true"
      DISCOVERY_PLAYWRIGHT_MCP = var.discovery_playwright_mcp
      LLM_PROVIDER             = var.llm_provider
      OPENAI_API_KEY           = var.openai_api_key
      OPENAI_MODEL_ID          = var.openai_model_id
      BRAVE_API_KEY            = var.brave_api_key
      BEDROCK_MODEL_ID         = var.bedrock_model_id
      BEDROCK_REGION           = var.bedrock_region
      AWS_REGION_NAME          = var.bedrock_region
      DISCOVERY_MAX_TURNS      = tostring(var.discovery_max_turns)
      DISCOVERY_MCP_TIMEOUT    = tostring(var.discovery_mcp_timeout)
      MCP_LOGGING              = var.mcp_logging
      PERSIST_DISCOVERY_RUNS   = var.persist_discovery_runs
      AURORA_CLUSTER_ARN       = var.aurora_cluster_arn
      AURORA_SECRET_ARN        = var.aurora_secret_arn
      DATABASE_NAME            = var.database_name
      DEFAULT_AWS_REGION       = var.aws_region
      DEEP_RESEARCH_ENABLED    = var.deep_research_enabled
      DEEP_RESEARCH_MAX_CANDIDATES = tostring(var.deep_research_max_candidates)
      DEEP_RESEARCH_MODE       = var.deep_research_mode
      DEEP_RESEARCH_QUEUE_URL  = var.deep_research_queue_url
    }
  }

  tags = {
    Project = "alphalens"
    Part    = "3_discovery"
  }
}

resource "aws_lambda_function_url" "discovery" {
  count              = local.discovery_deployed ? 1 : 0
  function_name      = aws_lambda_function.discovery[0].function_name
  authorization_type = "NONE"
}

resource "aws_lambda_permission" "allow_public_function_url_invoke" {
  count                    = local.discovery_deployed ? 1 : 0
  statement_id             = "AllowPublicFunctionInvokeViaUrl"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.discovery[0].function_name
  principal                = "*"
  invoked_via_function_url = true
}
