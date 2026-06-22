variable "aws_region" {
  description = "AWS region for AlphaLens database resources"
  type        = string
}

variable "database_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "alphalens"
}

variable "master_username" {
  description = "Master username for the Aurora cluster"
  type        = string
  default     = "alphalensadmin"
}

variable "engine_version" {
  description = "Aurora PostgreSQL engine version"
  type        = string
  default     = "15.12"
}

variable "min_capacity" {
  description = "Minimum Aurora Serverless v2 capacity (ACUs)"
  type        = number
  default     = 0.5
}

variable "max_capacity" {
  description = "Maximum Aurora Serverless v2 capacity (ACUs)"
  type        = number
  default     = 1.0
}

variable "backup_retention_period" {
  description = "Number of days to retain automated backups"
  type        = number
  default     = 7
}
