# Copyright AnyCompany, Inc. or its affiliates. All Rights Reserved.

# ─────────────────────────────────────────────
# Cognito User Pool
# ─────────────────────────────────────────────
resource "aws_cognito_user_pool" "main" {
  name = "customer-management-${var.environment}"

  password_policy {
    minimum_length                   = 8
    require_uppercase                = true
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  tags = {
    Environment = var.environment
    Project     = "customer-management-platform"
  }
}

resource "aws_cognito_user_pool_client" "main" {
  name         = "customer-management-client-${var.environment}"
  user_pool_id = aws_cognito_user_pool.main.id

  # No client secret — public client
  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]
}
