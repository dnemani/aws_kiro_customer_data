#!/usr/bin/env bash
# Copyright AnyCompany. All Rights Reserved.
#
# One-time bootstrap of the Terraform remote-state backend:
#   - a versioned, encrypted, private S3 bucket for state
#   - a DynamoDB table for state locking
#
# The bucket creation requires S3 permissions the customer-platform-deployer user
# does NOT have, so run this with an IAM-admin/power profile for account
# 114943206720 (override via AWS_PROFILE). The DynamoDB lock table name matches
# the existing "customer_records*" grant so the deployer can manage it too.
#
# Usage:
#   AWS_PROFILE=<admin-profile> ./scripts/bootstrap_backend.sh
set -euo pipefail

REGION="${REGION:-us-east-1}"
BUCKET="${BUCKET:-customer-platform-tfstate-114943206720}"
LOCK_TABLE="${LOCK_TABLE:-customer_records_tflock}"
PROFILE_ARG=""
if [[ -n "${AWS_PROFILE:-}" ]]; then
  PROFILE_ARG="--profile ${AWS_PROFILE}"
fi

echo "==> Region:      ${REGION}"
echo "==> Bucket:      ${BUCKET}"
echo "==> Lock table:  ${LOCK_TABLE}"
echo "==> Profile:     ${AWS_PROFILE:-<default>}"
echo

# ── S3 state bucket ──────────────────────────────────────────────────────────
if aws s3api head-bucket --bucket "${BUCKET}" ${PROFILE_ARG} 2>/dev/null; then
  echo "S3 bucket ${BUCKET} already exists — skipping create."
else
  echo "Creating S3 bucket ${BUCKET}..."
  if [[ "${REGION}" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "${BUCKET}" --region "${REGION}" ${PROFILE_ARG}
  else
    aws s3api create-bucket --bucket "${BUCKET}" --region "${REGION}" \
      --create-bucket-configuration LocationConstraint="${REGION}" ${PROFILE_ARG}
  fi
fi

echo "Enabling versioning..."
aws s3api put-bucket-versioning --bucket "${BUCKET}" \
  --versioning-configuration Status=Enabled ${PROFILE_ARG}

echo "Enabling default encryption (SSE-S3/AES256)..."
aws s3api put-bucket-encryption --bucket "${BUCKET}" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}' ${PROFILE_ARG}

echo "Blocking all public access..."
aws s3api put-public-access-block --bucket "${BUCKET}" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true \
  ${PROFILE_ARG}

# ── DynamoDB lock table ──────────────────────────────────────────────────────
if aws dynamodb describe-table --table-name "${LOCK_TABLE}" --region "${REGION}" ${PROFILE_ARG} >/dev/null 2>&1; then
  echo "DynamoDB table ${LOCK_TABLE} already exists — skipping create."
else
  echo "Creating DynamoDB lock table ${LOCK_TABLE}..."
  aws dynamodb create-table \
    --table-name "${LOCK_TABLE}" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "${REGION}" ${PROFILE_ARG}
  echo "Waiting for table to become ACTIVE..."
  aws dynamodb wait table-exists --table-name "${LOCK_TABLE}" --region "${REGION}" ${PROFILE_ARG}
fi

echo
echo "Bootstrap complete. Next:"
echo "  cd infra"
echo "  terraform init -backend-config=envs/dev.s3.tfbackend"
