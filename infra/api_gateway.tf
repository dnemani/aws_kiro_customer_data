# Copyright AnyCompany, Inc. or its affiliates. All Rights Reserved.

# ─────────────────────────────────────────────
# API Gateway — REST API
# ─────────────────────────────────────────────
resource "aws_api_gateway_rest_api" "customers" {
  name = "customer-management-api-${var.environment}"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Environment = var.environment
    Project     = "customer-management-platform"
  }
}

# Lambda TOKEN Authorizer (300-second TTL cache)
resource "aws_api_gateway_authorizer" "cognito_jwt" {
  name                             = "cognito-jwt-authorizer"
  rest_api_id                      = aws_api_gateway_rest_api.customers.id
  authorizer_uri                   = aws_lambda_function.authorizer.invoke_arn
  authorizer_result_ttl_in_seconds = 300
  type                             = "TOKEN"
  identity_source                  = "method.request.header.Authorization"
}

# ─────────────────────────────────────────────
# /customers resource
# ─────────────────────────────────────────────
resource "aws_api_gateway_resource" "customers" {
  rest_api_id = aws_api_gateway_rest_api.customers.id
  parent_id   = aws_api_gateway_rest_api.customers.root_resource_id
  path_part   = "customers"
}

# POST /customers
resource "aws_api_gateway_method" "customers_post" {
  rest_api_id   = aws_api_gateway_rest_api.customers.id
  resource_id   = aws_api_gateway_resource.customers.id
  http_method   = "POST"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.cognito_jwt.id
}

resource "aws_api_gateway_integration" "customers_post" {
  rest_api_id             = aws_api_gateway_rest_api.customers.id
  resource_id             = aws_api_gateway_resource.customers.id
  http_method             = aws_api_gateway_method.customers_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.customers.invoke_arn
}

# GET /customers
resource "aws_api_gateway_method" "customers_get" {
  rest_api_id   = aws_api_gateway_rest_api.customers.id
  resource_id   = aws_api_gateway_resource.customers.id
  http_method   = "GET"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.cognito_jwt.id
}

resource "aws_api_gateway_integration" "customers_get" {
  rest_api_id             = aws_api_gateway_rest_api.customers.id
  resource_id             = aws_api_gateway_resource.customers.id
  http_method             = aws_api_gateway_method.customers_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.customers.invoke_arn
}

# ─────────────────────────────────────────────
# /customers/{customer_id} resource
# ─────────────────────────────────────────────
resource "aws_api_gateway_resource" "customer_id" {
  rest_api_id = aws_api_gateway_rest_api.customers.id
  parent_id   = aws_api_gateway_resource.customers.id
  path_part   = "{customer_id}"
}

# GET /customers/{customer_id}
resource "aws_api_gateway_method" "customer_id_get" {
  rest_api_id   = aws_api_gateway_rest_api.customers.id
  resource_id   = aws_api_gateway_resource.customer_id.id
  http_method   = "GET"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.cognito_jwt.id
}

resource "aws_api_gateway_integration" "customer_id_get" {
  rest_api_id             = aws_api_gateway_rest_api.customers.id
  resource_id             = aws_api_gateway_resource.customer_id.id
  http_method             = aws_api_gateway_method.customer_id_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.customers.invoke_arn
}

# PUT /customers/{customer_id}
resource "aws_api_gateway_method" "customer_id_put" {
  rest_api_id   = aws_api_gateway_rest_api.customers.id
  resource_id   = aws_api_gateway_resource.customer_id.id
  http_method   = "PUT"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.cognito_jwt.id
}

resource "aws_api_gateway_integration" "customer_id_put" {
  rest_api_id             = aws_api_gateway_rest_api.customers.id
  resource_id             = aws_api_gateway_resource.customer_id.id
  http_method             = aws_api_gateway_method.customer_id_put.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.customers.invoke_arn
}

# DELETE /customers/{customer_id}
resource "aws_api_gateway_method" "customer_id_delete" {
  rest_api_id   = aws_api_gateway_rest_api.customers.id
  resource_id   = aws_api_gateway_resource.customer_id.id
  http_method   = "DELETE"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.cognito_jwt.id
}

resource "aws_api_gateway_integration" "customer_id_delete" {
  rest_api_id             = aws_api_gateway_rest_api.customers.id
  resource_id             = aws_api_gateway_resource.customer_id.id
  http_method             = aws_api_gateway_method.customer_id_delete.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.customers.invoke_arn
}

# ─────────────────────────────────────────────
# Deployment and Stage
# ─────────────────────────────────────────────
resource "aws_api_gateway_deployment" "v1" {
  rest_api_id = aws_api_gateway_rest_api.customers.id

  depends_on = [
    aws_api_gateway_integration.customers_post,
    aws_api_gateway_integration.customers_get,
    aws_api_gateway_integration.customer_id_get,
    aws_api_gateway_integration.customer_id_put,
    aws_api_gateway_integration.customer_id_delete,
  ]

  lifecycle {
    create_before_destroy = true
  }
}

# CloudWatch log group for API Gateway access logs
# Created unconditionally; only attached to the stage in production
resource "aws_cloudwatch_log_group" "apigw_access_logs" {
  name              = "/aws/apigateway/customer-management-${var.environment}"
  retention_in_days = 30
}

resource "aws_api_gateway_stage" "v1" {
  deployment_id = aws_api_gateway_deployment.v1.id
  rest_api_id   = aws_api_gateway_rest_api.customers.id
  stage_name    = "v1"

  # Requirement 7.3: enforce HTTPS — disable HTTP entirely
  # API Gateway REST APIs only accept HTTPS by default; no additional setting needed.

  # Requirement 7.5: CloudWatch access logging in production only
  dynamic "access_log_settings" {
    for_each = var.environment == "prod" ? [1] : []
    content {
      destination_arn = aws_cloudwatch_log_group.apigw_access_logs.arn
      format = jsonencode({
        requestId    = "$context.requestId"
        httpMethod   = "$context.httpMethod"
        resourcePath = "$context.resourcePath"
        status       = "$context.status"
        requestTime  = "$context.requestTime"
      })
    }
  }

  tags = {
    Environment = var.environment
    Project     = "customer-management-platform"
  }
}
