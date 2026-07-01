# Copyright AnyCompany, Inc. or its affiliates. All Rights Reserved.

output "api_invoke_url" {
  description = "Base URL for the Customer Management API"
  value       = aws_api_gateway_stage.v1.invoke_url
}

output "cognito_user_pool_id" {
  description = "ID of the Cognito User Pool"
  value       = aws_cognito_user_pool.main.id
}

output "cognito_app_client_id" {
  description = "ID of the Cognito App Client"
  value       = aws_cognito_user_pool_client.main.id
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB customer records table"
  value       = aws_dynamodb_table.customer_records.name
}
