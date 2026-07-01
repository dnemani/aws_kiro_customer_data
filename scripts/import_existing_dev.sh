#!/usr/bin/env bash
# Copyright AnyCompany. All Rights Reserved.
#
# Import the dev resources that already exist in AWS account 114943206720 into
# Terraform state, so a subsequent `terraform apply` reconciles instead of
# trying to recreate them.
#
# Prerequisites:
#   1. The S3 + DynamoDB backend has been bootstrapped (scripts/bootstrap_backend.sh).
#   2. The customer-platform-deployer policy has been extended with the S3 +
#      DynamoDB-lock statements (infra/deployer-policy-additions.json).
#   3. Backend initialised:  cd infra && terraform init -backend-config=envs/dev.s3.tfbackend
#
# Usage (from repo root):
#   AWS_PROFILE=customer-platform ./scripts/import_existing_dev.sh
#
# Resource IDs below were captured live from the existing dev deployment.
set -euo pipefail

cd "$(dirname "$0")/../infra"

VARS="-var-file=envs/dev.tfvars"
imp() {
  echo "==> import $1"
  terraform import ${VARS} "$1" "$2"
}

# ── DynamoDB ─────────────────────────────────────────────────────────────────
imp aws_dynamodb_table.customer_records customer_records_dev

# ── IAM roles + inline policies (format: <role-name>:<policy-name>) ───────────
imp aws_iam_role.customers_lambda            customers-lambda-role-dev
imp aws_iam_role.authorizer_lambda           authorizer-lambda-role-dev
imp aws_iam_role_policy.customers_lambda_dynamo "customers-lambda-role-dev:customers-lambda-dynamo-dev"
imp aws_iam_role_policy.customers_lambda_logs   "customers-lambda-role-dev:customers-lambda-logs-dev"
imp aws_iam_role_policy.authorizer_lambda_logs  "authorizer-lambda-role-dev:authorizer-lambda-logs-dev"

# ── Cognito (client format: <user-pool-id>/<client-id>) ───────────────────────
imp aws_cognito_user_pool.main        us-east-1_GKF6gO5De
imp aws_cognito_user_pool_client.main us-east-1_GKF6gO5De/k2p8rn994g7cfsoej96p1iqlt

# ── API Gateway (resource format: <rest-api-id>/<resource-id>) ────────────────
imp aws_api_gateway_rest_api.customers v87sbmnj0b
imp aws_api_gateway_resource.customers    v87sbmnj0b/tyj7kq
imp aws_api_gateway_resource.customer_id  v87sbmnj0b/ojujrd

echo
echo "Imports complete. Now review the remaining plan:"
echo "  cd infra && terraform plan ${VARS}"
echo
echo "Expected: the Lambda functions, lambda permissions, API Gateway methods/"
echo "integrations/authorizer/deployment/stage, and the access-log group remain"
echo "to be created (they do not exist yet). Imported resources may also show"
echo "in-place attribute updates to match the Terraform config."
