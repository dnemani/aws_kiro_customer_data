# Copyright AnyCompany, Inc. or its affiliates. All Rights Reserved.

# ─────────────────────────────────────────────
# IAM — Lambda execution trust policy (shared)
# ─────────────────────────────────────────────
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ─────────────────────────────────────────────
# IAM — Authorizer Lambda role
# ─────────────────────────────────────────────
resource "aws_iam_role" "authorizer_lambda" {
  name               = "authorizer-lambda-role-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags = {
    Environment = var.environment
    Project     = "customer-management-platform"
  }
}

resource "aws_iam_role_policy" "authorizer_lambda_logs" {
  name = "authorizer-lambda-logs-${var.environment}"
  role = aws_iam_role.authorizer_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# ─────────────────────────────────────────────
# IAM — Customers Lambda role
# ─────────────────────────────────────────────
resource "aws_iam_role" "customers_lambda" {
  name               = "customers-lambda-role-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags = {
    Environment = var.environment
    Project     = "customer-management-platform"
  }
}

resource "aws_iam_role_policy" "customers_lambda_dynamo" {
  name = "customers-lambda-dynamo-${var.environment}"
  role = aws_iam_role.customers_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        # Requirement 8.5: only the DynamoDB actions the Lambda explicitly invokes
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Scan",
          "dynamodb:Query",
        ]
        Resource = [
          aws_dynamodb_table.customer_records.arn,
          "${aws_dynamodb_table.customer_records.arn}/index/*",
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "customers_lambda_logs" {
  name = "customers-lambda-logs-${var.environment}"
  role = aws_iam_role.customers_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}
