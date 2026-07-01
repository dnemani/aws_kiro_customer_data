# Copyright AnyCompany, Inc. or its affiliates. All Rights Reserved.

# ─────────────────────────────────────────────
# DynamoDB — Customer Records Table
# ─────────────────────────────────────────────
resource "aws_dynamodb_table" "customer_records" {
  name         = var.customers_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "customer_id"

  attribute {
    name = "customer_id"
    type = "S"
  }

  attribute {
    name = "email"
    type = "S"
  }

  global_secondary_index {
    name            = var.email_index_name
    hash_key        = "email"
    projection_type = "ALL"
  }

  tags = {
    Environment = var.environment
    Project     = "customer-management-platform"
  }
}
