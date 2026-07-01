# Copyright AnyCompany. All Rights Reserved.
#
# Remote state backend (S3 + DynamoDB lock).
#
# Bucket, region, DynamoDB lock table, encryption, and the per-environment state
# key are supplied at init time via a backend config file, e.g.:
#
#   terraform init -backend-config=envs/dev.s3.tfbackend
#   terraform init -backend-config=envs/prod.s3.tfbackend
#
# The backing S3 bucket and DynamoDB lock table must exist before running init;
# create them once with scripts/bootstrap_backend.sh.
terraform {
  backend "s3" {}
}
