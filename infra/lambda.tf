# Copyright AnyCompany, Inc. or its affiliates. All Rights Reserved.

# ─────────────────────────────────────────────
# Package source code into zip archives
# ─────────────────────────────────────────────
# The authorizer package includes vendored third-party dependencies
# (python-jose + cryptography) that are NOT in the Lambda runtime. Those deps are
# installed into build/authorizer by scripts/build_lambdas.sh, which MUST be run
# before `terraform plan`/`apply`. This archive_file zips that prepared directory.
data "archive_file" "authorizer_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../build/authorizer"
  output_path = "${path.module}/../build/lambda_authorizer.zip"
}

data "archive_file" "customers_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/customers"
  output_path = "${path.module}/../src/customers/lambda_customers.zip"
  excludes    = ["lambda_customers.zip", "__pycache__", "requirements.txt"]
}

# ─────────────────────────────────────────────
# Lambda — Authorizer
# ─────────────────────────────────────────────
resource "aws_lambda_function" "authorizer" {
  function_name    = "customer-management-authorizer-${var.environment}"
  filename         = data.archive_file.authorizer_zip.output_path
  source_code_hash = data.archive_file.authorizer_zip.output_base64sha256
  role             = aws_iam_role.authorizer_lambda.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"

  environment {
    variables = {
      COGNITO_USER_POOL_ID  = aws_cognito_user_pool.main.id
      COGNITO_REGION        = var.aws_region
      COGNITO_APP_CLIENT_ID = aws_cognito_user_pool_client.main.id
    }
  }

  tags = {
    Environment = var.environment
    Project     = "customer-management-platform"
  }
}

# Allow API Gateway to invoke the Authorizer Lambda
resource "aws_lambda_permission" "authorizer_apigw" {
  statement_id  = "AllowAPIGatewayInvokeAuthorizer"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.authorizer.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.customers.execution_arn}/*"
}

# ─────────────────────────────────────────────
# Lambda — Customers CRUD
# ─────────────────────────────────────────────
resource "aws_lambda_function" "customers" {
  function_name    = "customer-management-customers-${var.environment}"
  filename         = data.archive_file.customers_zip.output_path
  source_code_hash = data.archive_file.customers_zip.output_base64sha256
  role             = aws_iam_role.customers_lambda.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"

  environment {
    variables = {
      TABLE_NAME       = var.customers_table_name
      EMAIL_INDEX_NAME = var.email_index_name
    }
  }

  tags = {
    Environment = var.environment
    Project     = "customer-management-platform"
  }
}

# Allow API Gateway to invoke the Customers Lambda
resource "aws_lambda_permission" "customers_apigw" {
  statement_id  = "AllowAPIGatewayInvokeCustomers"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.customers.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.customers.execution_arn}/*"
}
