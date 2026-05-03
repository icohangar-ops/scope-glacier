# Scope.Glacier Terraform Variables

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "scope-glacier"
}

variable "glue_database" {
  description = "AWS Glue database name"
  type        = string
  default     = "scope_glacier"
}

variable "bedrock_model_id" {
  description = "Amazon Bedrock model ID for Converse API"
  type        = string
  default     = "anthropic.claude-3-haiku-20240307-v1:0"
}

variable "eia_api_key" {
  description = "US EIA Open Data API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "alpha_vantage_key" {
  description = "AlphaVantage API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "fred_api_key" {
  description = "FRED API key"
  type        = string
  default     = ""
  sensitive   = true
}
