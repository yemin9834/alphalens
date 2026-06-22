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
  agents = toset(["orchestrator", "validator", "analyst", "portfolio", "discovery", "qa"])
}

# ========================================
# SQS Queue
# ========================================

resource "aws_sqs_queue" "analysis_jobs_dlq" {
  name = "alphalens-analysis-jobs-dlq"

  tags = {
    Project = "alphalens"
    Part    = "2_agents"
  }
}

resource "aws_sqs_queue" "analysis_jobs" {
  name                       = "alphalens-analysis-jobs"
  delay_seconds              = 0
  max_message_size           = 262144
  message_retention_seconds  = 86400
  receive_wait_time_seconds  = 10
  visibility_timeout_seconds = 910

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.analysis_jobs_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Project = "alphalens"
    Part    = "2_agents"
  }
}

resource "aws_sqs_queue" "deep_research_jobs_dlq" {
  name = "alphalens-deep-research-jobs-dlq"

  tags = {
    Project = "alphalens"
    Part    = "2_agents"
  }
}

resource "aws_sqs_queue" "deep_research_jobs" {
  name                       = "alphalens-deep-research-jobs"
  delay_seconds              = 0
  max_message_size           = 262144
  message_retention_seconds  = 86400
  receive_wait_time_seconds  = 10
  visibility_timeout_seconds = 900

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.deep_research_jobs_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Project = "alphalens"
    Part    = "2_agents"
  }
}

# ========================================
# IAM Role
# ========================================

resource "aws_iam_role" "lambda_agents_role" {
  name = "alphalens-lambda-agents-role"

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
    Part    = "2_agents"
  }
}

resource "aws_iam_role_policy" "lambda_agents_policy" {
  name = "alphalens-lambda-agents-policy"
  role = aws_iam_role.lambda_agents_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.analysis_jobs.arn
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.deep_research_jobs.arn
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:alphalens-*"
      },
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
      },
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

resource "aws_iam_role_policy_attachment" "lambda_agents_basic" {
  role       = aws_iam_role.lambda_agents_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ========================================
# S3 Lambda packages
# ========================================

resource "aws_s3_bucket" "lambda_packages" {
  bucket = "alphalens-lambda-packages-${data.aws_caller_identity.current.account_id}"

  tags = {
    Project = "alphalens"
    Part    = "2_agents"
  }
}

resource "aws_s3_object" "lambda_packages" {
  for_each = local.agents

  bucket = aws_s3_bucket.lambda_packages.id
  key    = "${each.key}/${each.key}_lambda.zip"
  source = "${path.module}/../../backend/${each.key}/${each.key}_lambda.zip"
  etag   = fileexists("${path.module}/../../backend/${each.key}/${each.key}_lambda.zip") ? filemd5("${path.module}/../../backend/${each.key}/${each.key}_lambda.zip") : null

  tags = {
    Project = "alphalens"
    Part    = "2_agents"
    Agent   = each.key
  }
}

locals {
  agent_env = {
    AURORA_CLUSTER_ARN = var.aurora_cluster_arn
    AURORA_SECRET_ARN  = var.aurora_secret_arn
    DATABASE_NAME      = var.database_name
    BEDROCK_MODEL_ID   = var.bedrock_model_id
    BEDROCK_REGION     = var.bedrock_region
    DEFAULT_AWS_REGION = var.aws_region
    AWS_REGION_NAME    = var.bedrock_region
    LLM_PROVIDER       = var.llm_provider
    OPENAI_API_KEY     = var.openai_api_key
    OPENAI_MODEL_ID    = var.openai_model_id
  }

  lambda_adapter_layer_x86 = "arn:aws:lambda:${var.aws_region}:753240598075:layer:LambdaAdapterLayerX86:27"
}

# ========================================
# Lambda functions
# ========================================

resource "aws_lambda_function" "orchestrator" {
  function_name    = "alphalens-orchestrator"
  role             = aws_iam_role.lambda_agents_role.arn
  s3_bucket        = aws_s3_bucket.lambda_packages.id
  s3_key           = aws_s3_object.lambda_packages["orchestrator"].key
  source_code_hash = fileexists("${path.module}/../../backend/orchestrator/orchestrator_lambda.zip") ? filebase64sha256("${path.module}/../../backend/orchestrator/orchestrator_lambda.zip") : null
  handler          = "lambda_handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 900
  memory_size      = 2048

  environment {
    variables = merge(local.agent_env, {
      VALIDATOR_FUNCTION       = "alphalens-validator"
      ANALYST_FUNCTION         = "alphalens-analyst"
      PORTFOLIO_FUNCTION       = "alphalens-portfolio"
      DISCOVERY_FUNCTION       = "alphalens-discovery"
      DISCOVERY_SERVICE_URL    = var.discovery_service_url
      USE_LLM_ORCHESTRATION       = tostring(var.use_llm_orchestration)
      USE_LLM_ANALYST_NARRATIVE   = tostring(var.use_llm_analyst_narrative)
    })
  }

  tags = {
    Project = "alphalens"
    Part    = "2_agents"
    Agent   = "orchestrator"
  }

  depends_on = [aws_s3_object.lambda_packages["orchestrator"]]
}

resource "aws_lambda_event_source_mapping" "orchestrator_sqs" {
  event_source_arn = aws_sqs_queue.analysis_jobs.arn
  function_name    = aws_lambda_function.orchestrator.arn
  batch_size       = 1
}

resource "aws_lambda_function" "validator" {
  function_name    = "alphalens-validator"
  role             = aws_iam_role.lambda_agents_role.arn
  s3_bucket        = aws_s3_bucket.lambda_packages.id
  s3_key           = aws_s3_object.lambda_packages["validator"].key
  source_code_hash = fileexists("${path.module}/../../backend/validator/validator_lambda.zip") ? filebase64sha256("${path.module}/../../backend/validator/validator_lambda.zip") : null
  handler          = "lambda_handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 180
  memory_size      = 1024

  environment {
    variables = merge(local.agent_env, {
      USE_LLM_VALIDATOR_NARRATIVE = tostring(var.use_llm_validator_narrative)
    })
  }

  tags = {
    Project = "alphalens"
    Part    = "2_agents"
    Agent   = "validator"
  }

  depends_on = [aws_s3_object.lambda_packages["validator"]]
}

resource "aws_lambda_function" "analyst" {
  function_name    = "alphalens-analyst"
  role             = aws_iam_role.lambda_agents_role.arn
  s3_bucket        = aws_s3_bucket.lambda_packages.id
  s3_key           = aws_s3_object.lambda_packages["analyst"].key
  source_code_hash = fileexists("${path.module}/../../backend/analyst/analyst_lambda.zip") ? filebase64sha256("${path.module}/../../backend/analyst/analyst_lambda.zip") : null
  handler          = "lambda_handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 300
  memory_size      = 1024

  environment {
    variables = merge(local.agent_env, {
      USE_LLM_ANALYST_NARRATIVE = tostring(var.use_llm_analyst_narrative)
    })
  }

  tags = {
    Project = "alphalens"
    Part    = "2_agents"
    Agent   = "analyst"
  }

  depends_on = [aws_s3_object.lambda_packages["analyst"]]
}

resource "aws_lambda_function" "portfolio" {
  function_name    = "alphalens-portfolio"
  role             = aws_iam_role.lambda_agents_role.arn
  s3_bucket        = aws_s3_bucket.lambda_packages.id
  s3_key           = aws_s3_object.lambda_packages["portfolio"].key
  source_code_hash = fileexists("${path.module}/../../backend/portfolio/portfolio_lambda.zip") ? filebase64sha256("${path.module}/../../backend/portfolio/portfolio_lambda.zip") : null
  handler          = "lambda_handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 300
  memory_size      = 1024

  environment {
    variables = merge(local.agent_env, {
      USE_LLM_PORTFOLIO_NARRATIVE = tostring(var.use_llm_portfolio)
      USE_LLM_PORTFOLIO           = tostring(var.use_llm_portfolio)
    })
  }

  tags = {
    Project = "alphalens"
    Part    = "2_agents"
    Agent   = "portfolio"
  }

  depends_on = [aws_s3_object.lambda_packages["portfolio"]]
}

resource "aws_lambda_function" "discovery" {
  function_name    = "alphalens-discovery"
  role             = aws_iam_role.lambda_agents_role.arn
  s3_bucket        = aws_s3_bucket.lambda_packages.id
  s3_key           = aws_s3_object.lambda_packages["discovery"].key
  source_code_hash = fileexists("${path.module}/../../backend/discovery/discovery_lambda.zip") ? filebase64sha256("${path.module}/../../backend/discovery/discovery_lambda.zip") : null
  handler          = "lambda_handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 120
  memory_size      = 512

  environment {
    variables = local.agent_env
  }

  tags = {
    Project = "alphalens"
    Part    = "2_agents"
    Agent   = "discovery"
  }

  depends_on = [aws_s3_object.lambda_packages["discovery"]]
}

resource "aws_lambda_function" "qa" {
  function_name    = "alphalens-qa"
  role             = aws_iam_role.lambda_agents_role.arn
  s3_bucket        = aws_s3_bucket.lambda_packages.id
  s3_key           = aws_s3_object.lambda_packages["qa"].key
  source_code_hash = fileexists("${path.module}/../../backend/qa/qa_lambda.zip") ? filebase64sha256("${path.module}/../../backend/qa/qa_lambda.zip") : null
  handler          = "lambda_handler.lambda_handler"
  runtime          = "python3.12"
  architectures    = ["x86_64"]
  timeout          = 120
  memory_size      = 512

  environment {
    variables = merge(local.agent_env, {
      USE_LLM_QA = tostring(var.use_llm_qa)
    })
  }

  tags = {
    Project = "alphalens"
    Part    = "2_agents"
    Agent   = "qa"
  }

  depends_on = [aws_s3_object.lambda_packages["qa"]]
}

resource "aws_s3_object" "deep_research_trigger_lambda" {
  bucket = aws_s3_bucket.lambda_packages.id
  key    = "deep_research_trigger/deep_research_trigger_lambda.zip"
  source = "${path.module}/../../backend/deep_research_trigger/deep_research_trigger_lambda.zip"
  etag   = fileexists("${path.module}/../../backend/deep_research_trigger/deep_research_trigger_lambda.zip") ? filemd5("${path.module}/../../backend/deep_research_trigger/deep_research_trigger_lambda.zip") : null

  tags = {
    Project = "alphalens"
    Part    = "2_agents"
    Agent   = "deep-research-trigger"
  }
}

resource "aws_lambda_function" "deep_research_trigger" {
  function_name    = "alphalens-deep-research-trigger"
  role             = aws_iam_role.lambda_agents_role.arn
  s3_bucket        = aws_s3_bucket.lambda_packages.id
  s3_key           = aws_s3_object.deep_research_trigger_lambda.key
  source_code_hash = fileexists("${path.module}/../../backend/deep_research_trigger/deep_research_trigger_lambda.zip") ? filebase64sha256("${path.module}/../../backend/deep_research_trigger/deep_research_trigger_lambda.zip") : null
  handler          = "lambda_handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 300
  memory_size      = 256

  environment {
    variables = {
      DISCOVERY_SERVICE_URL      = var.discovery_service_url
      DEEP_RESEARCH_HTTP_TIMEOUT = "300"
      DEFAULT_AWS_REGION         = var.aws_region
    }
  }

  tags = {
    Project = "alphalens"
    Part    = "2_agents"
    Agent   = "deep-research-trigger"
  }

  depends_on = [aws_s3_object.deep_research_trigger_lambda]
}

resource "aws_lambda_event_source_mapping" "deep_research_sqs" {
  event_source_arn = aws_sqs_queue.deep_research_jobs.arn
  function_name    = aws_lambda_function.deep_research_trigger.arn
  batch_size       = 1
}

resource "aws_cloudwatch_log_group" "agent_logs" {
  for_each = local.agents

  name              = "/aws/lambda/alphalens-${each.key}"
  retention_in_days = 7

  tags = {
    Project = "alphalens"
    Part    = "2_agents"
    Agent   = each.key
  }
}
