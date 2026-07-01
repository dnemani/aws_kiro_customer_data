# Copyright AnyCompany. All Rights Reserved.

variable "environment" {
  description = "Deployment environment name (e.g. dev, prod)"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region to deploy resources into"
  type        = string
  default     = "us-east-1"
}

variable "customers_table_name" {
  description = "Name of the DynamoDB table used to store customer records"
  type        = string
  default     = "customer_records"
}

variable "email_index_name" {
  description = "Name of the DynamoDB GSI used for email lookups"
  type        = string
  default     = "email-index"
}
