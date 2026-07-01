#!/usr/bin/env bash
#
# Copyright AnyCompany, Inc. or its affiliates. All Rights Reserved.
#
# Builds Lambda deployment artifacts that require third-party dependencies.
#
# The authorizer Lambda depends on python-jose (and its transitive deps such as
# cryptography), which are NOT part of the AWS Lambda Python runtime and must be
# vendored into the deployment package. Dependencies are fetched as Linux
# (manylinux) wheels targeting the Lambda python3.12 runtime, regardless of the
# host OS — installing them natively on macOS would produce incompatible
# binaries for the compiled `cryptography` dependency.
#
# Terraform (infra/lambda.tf) zips `build/authorizer` via an archive_file data
# source, so this script MUST be run before `terraform plan` / `terraform apply`.
#
# The customers Lambda has no third-party dependencies (it uses only boto3, which
# the runtime provides), so Terraform packages it directly from src/ and it is
# not handled here.
#
# Usage:
#   ./scripts/build_lambdas.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="${ROOT}/src/authorizer"
BUILD_DIR="${ROOT}/build/authorizer"
PY_VERSION="3.12"

echo "==> Cleaning ${BUILD_DIR}"
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

echo "==> Installing authorizer dependencies (manylinux2014_x86_64, cp${PY_VERSION//./}) "
python3 -m pip install \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version "${PY_VERSION}" \
  --only-binary=:all: \
  --upgrade \
  -r "${SRC_DIR}/requirements.txt" \
  -t "${BUILD_DIR}"

echo "==> Copying handler source"
cp "${SRC_DIR}/lambda_function.py" "${BUILD_DIR}/"

# Drop bytecode/metadata that only bloats the package.
find "${BUILD_DIR}" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true

echo "==> Done. ${BUILD_DIR} is ready for Terraform to zip."
