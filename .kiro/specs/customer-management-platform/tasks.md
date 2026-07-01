# Implementation Plan: Customer Management Platform

## Overview

Implement a serverless customer management REST API on AWS using Python Lambda functions, API Gateway, DynamoDB, and Cognito — with all infrastructure defined in Terraform. The plan builds incrementally: shared utilities first, then the Lambda Authorizer, then the Customers CRUD Lambda, then infrastructure, and finally integration wiring and tests.

## Deployment Status

All implementation tasks (1–9) are complete, and the **dev environment is deployed** to
AWS account `114943206720` (region `us-east-1`).

**Remote state** (S3 + DynamoDB lock), provisioned via `scripts/bootstrap_backend.sh`:
- Bucket: `customer-platform-tfstate-114943206720`
- Lock table: `customer_records_tflock`
- Init: `cd infra && terraform init -backend-config=envs/dev.s3.tfbackend`

**Deployed dev resources** (`terraform apply -var-file=envs/dev.tfvars`; state clean, no drift):
- API invoke URL: `https://v87sbmnj0b.execute-api.us-east-1.amazonaws.com/v1`
- Cognito user pool: `us-east-1_GKF6gO5De`
- Cognito app client: `6a8qqf8he5075bucjnb7uc47g2`
- DynamoDB table: `customer_records_dev`

**Notes for future work:**
- Pre-existing dev resources were imported into state via `scripts/import_existing_dev.sh`
  (idempotent). Any fresh account can skip this and just `apply`.
- The API Gateway access-log group is now created **prod-only** (`count` in
  `infra/api_gateway.tf`), since dev does not attach access logging.
- **Prod is not yet deployed.** Prod deploy needs: `terraform init -backend-config=envs/prod.s3.tfbackend`,
  then `apply -var-file=envs/prod.tfvars`. Because prod creates the CloudWatch log group,
  the deployer IAM policy must grant `logs:DescribeLogGroups` on `Resource: "*"`
  (wildcard-only action) — see `infra/deployer-policy.json`.
- The IAM policy the deployer uses is version-controlled at `infra/deployer-policy.json`.

## Tasks

- [x] 1. Set up project structure and shared utilities
  - [x] 1.1 Add copyright header to existing source files and create `src/customers/utils.py` with shared helper functions
    - Implement `is_valid_uuid4(value) -> bool` using the `uuid` standard library
    - Implement `build_response(status_code, body) -> dict` that returns an API Gateway proxy response with sanitized JSON body (no stack traces, ARNs, or DynamoDB error codes)
    - Implement `get_dynamodb_table()` returning a `boto3` DynamoDB `Table` resource driven by `TABLE_NAME` and `AWS_REGION` environment variables
    - Add copyright header comment to all `.py` files touched in this task
    - _Requirements: 7.4_

  - [x] 1.2 Implement `validate_customer_body(body) -> dict[str, str]` in `src/customers/utils.py`
    - Validate `name`: required, non-empty string, max 200 characters
    - Validate `email`: required, RFC 5322 format (use `re` module pattern)
    - Validate `phone` (optional): digits, spaces, hyphens, plus signs, parentheses only; min 7, max 20 characters
    - Validate `address` (optional): non-empty string, max 500 characters
    - Return a dict mapping each failing field name to a human-readable reason string; return empty dict on success
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x]* 1.3 Write property tests for shared utilities
    - Create `tests/unit/test_customers_validation.py`
    - **Property 5: Invalid input is always rejected with field-level errors**
      - Use `@given` with Hypothesis strategies to generate invalid customer body dicts (missing required fields, name > 200 chars, non-RFC-5322 emails, invalid phone strings) — verify `validate_customer_body` returns non-empty dict with correct field keys
      - **Validates: Requirements 2.3, 4.3, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**
    - **Property 10: Non-UUID-v4 strings are always rejected**
      - Use `@given(st.text())` filtered to exclude valid UUID v4 strings — verify `is_valid_uuid4` returns `False`
      - **Validates: Requirements 5.4**
    - Include boundary-value example tests: `name` at 1, 200, 201 chars; `phone` at 6, 7, 20, 21 chars; `address` at 1, 500, 501 chars
    - Add `# Feature: customer-management-platform` comment tags to each property test
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 5.4_

- [x] 2. Implement the Lambda Authorizer
  - [x] 2.1 Implement JWT validation logic in `src/authorizer/lambda_function.py`
    - Add copyright header
    - Fetch and cache the Cognito User Pool JWKS (cache in module-level variable for container lifetime)
    - Implement `validate_token(token, jwks, issuer, audience) -> dict` that validates JWT signature, `exp`, `iss`, and `aud` using `python-jose`
    - Implement `build_policy(principal_id, effect, resource) -> dict` that constructs an IAM policy document with `execute-api:Invoke` action
    - In `lambda_handler`: extract Bearer token from `authorizationToken`, call validate, return Allow policy on success, raise `Exception("Unauthorized")` on any failure (expired, malformed, missing, wrong key, wrong `iss`/`aud`, JWKS fetch failure)
    - Read `COGNITO_USER_POOL_ID`, `COGNITO_REGION`, and `COGNITO_APP_CLIENT_ID` from environment variables
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x]* 2.2 Write property tests for the Lambda Authorizer
    - Create `tests/unit/test_authorizer.py`
    - **Property 1: Valid JWTs are always permitted**
      - Use `@given` to generate valid JWT payloads with varying `sub`, custom claims, and realistic `exp` values, signed with the test key — verify `Effect: Allow` returned
      - **Validates: Requirements 1.1**
    - **Property 2: Invalid JWTs are always denied**
      - Use `@given` with `st.text()` (arbitrary strings) and constructs for expired tokens, wrong-key-signed tokens, wrong `iss`/`aud` tokens — verify `Effect: Deny` or `Unauthorized` raised
      - **Validates: Requirements 1.2, 1.3, 1.4, 1.5**
    - Include example tests for missing `Authorization` header and absent `Bearer ` prefix
    - Add `# Feature: customer-management-platform` comment tags to each property test
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 3. Checkpoint — Ensure all unit tests pass so far
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement the Customers Lambda — core CRUD handlers
  - [x] 4.1 Implement `create_customer` handler in `src/customers/lambda_function.py`
    - Add copyright header and `lambda_handler` router that dispatches by `httpMethod` and `resource`
    - In `create_customer`: call `validate_customer_body`; on validation errors return 400 with `{"error": "Validation failed", "fields": {...}}`
    - Generate UUID v4 `customer_id` with `uuid.uuid4()`
    - Set `created_at` to current UTC time in ISO 8601 format
    - Check for duplicate email using a DynamoDB `query` on the `email-index` GSI; return 409 on conflict
    - Write item with `put_item`; return 201 with full customer record on success
    - On DynamoDB write error return 500 via `build_response` with sanitized message; do NOT include `customer_id` in 500 response
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x]* 4.2 Write property tests for `create_customer`
    - In `tests/unit/test_customers_crud.py` (create file), mock DynamoDB with `moto`
    - **Property 3: Valid customer creation always succeeds with a UUID v4 ID**
      - `@given` valid customer create bodies (varying name, email, optional fields) — verify HTTP 201 and `is_valid_uuid4(response["customer_id"])` is `True`
      - **Validates: Requirements 2.1, 2.2**
    - **Property 4: Created records have a valid ISO 8601 UTC `created_at` timestamp**
      - `@given` valid create bodies — verify `created_at` is parseable by `datetime.fromisoformat`
      - **Validates: Requirements 2.5**
    - Add example test for duplicate email → 409 and DynamoDB write error → 500 (no `customer_id` in body)
    - Add `# Feature: customer-management-platform` comment tags
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 4.3 Implement `get_customer` and `list_customers` handlers
    - `get_customer`: validate `customer_id` is UUID v4 (400 on failure), call `get_item`; return 200 with full record or 404 if not found; return 503 on DynamoDB error
    - `list_customers`: call `scan` with `Limit=100`; if `LastEvaluatedKey` present, base64-encode it and return as `nextToken` in response; decode inbound `nextToken` query param as `ExclusiveStartKey`; return 503 on DynamoDB error
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x]* 4.4 Write property tests for `get_customer`
    - **Property 6: Create-then-retrieve round trip preserves all fields**
      - `@given` valid customer records — create then GET, verify all fields in create request appear unchanged in GET response, plus `customer_id` and `created_at`
      - **Validates: Requirements 3.1**
    - **Property 7: GET on non-existent ID always returns 404**
      - `@given` UUID v4 strings not present in the mocked table — verify GET returns 404 with error message and no customer data fields
      - **Validates: Requirements 3.2**
    - Add example test: pagination with > 100 records returns `nextToken`; fetching with valid `nextToken` returns next page
    - Add `# Feature: customer-management-platform` comment tags
    - _Requirements: 3.1, 3.2, 3.3, 3.5_

  - [x] 4.5 Implement `update_customer` handler
    - Validate `customer_id` path param is UUID v4 (400 on failure)
    - Call `validate_customer_body` on request body; return 400 with field-level errors on failure
    - Check for duplicate email on `email-index` GSI for a different `customer_id`; return 409 on conflict
    - Call `get_item` to confirm customer exists; return 404 if not found
    - Call `update_item` preserving original `customer_id` and `created_at` regardless of request body values; set `updated_at` to current UTC ISO 8601
    - Return 200 with the full updated record including all server-generated fields
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x]* 4.6 Write property tests for `update_customer`
    - **Property 8: Update preserves immutable fields**
      - `@given` valid existing customers plus valid update bodies (optionally including override attempts for `customer_id` and `created_at`) — verify response contains original `customer_id` and `created_at` unchanged; verify `updated_at` is valid ISO 8601 and `updated_at >= created_at`
      - **Validates: Requirements 4.5, 4.6**
    - Add example test: PUT with non-existent `customer_id` → 404; PUT with duplicate email for different customer → 409
    - Add `# Feature: customer-management-platform` comment tags
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x] 4.7 Implement `delete_customer` handler
    - Validate `customer_id` path param is UUID v4; return 400 with error identifying the malformed ID if invalid
    - Call `get_item` to confirm existence; return 404 with error message (no confirmation) if not found
    - Call `delete_item`; return 200 with `{"message": "Customer <customer_id> deleted successfully"}`
    - Return 503 on DynamoDB error with sanitized message
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x]* 4.8 Write property tests for `delete_customer`
    - **Property 9: DELETE removes the record and makes it unretrievable**
      - `@given` valid customer records — create, DELETE (verify 200 with confirmation message), GET (verify 404)
      - **Validates: Requirements 5.1**
    - **Property 10: DELETE with non-UUID-v4 ID always returns 400**
      - `@given` arbitrary strings that are not valid UUID v4 — verify DELETE returns 400 with error message identifying the malformed ID
      - **Validates: Requirements 5.4**
    - Add `# Feature: customer-management-platform` comment tags
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x]* 4.9 Write property test for sanitized error responses
    - **Property 11: Responses never expose internal error details**
      - `@given` various error conditions (mocked DynamoDB `ClientError` on write, read, and delete paths; invalid inputs) — verify no response body `json.dumps` output contains substrings matching stack traces, ARNs (`arn:`), or DynamoDB error code patterns
      - **Validates: Requirements 7.4**
    - Add `# Feature: customer-management-platform` comment tags
    - _Requirements: 7.4_

- [x] 5. Checkpoint — Ensure all unit and property tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Define Terraform infrastructure in `infra/main.tf`
  - [x] 6.1 Define DynamoDB table resource
    - `aws_dynamodb_table` with `PAY_PER_REQUEST` billing, `customer_id` String partition key, no sort key
    - GSI `email-index` with `email` String partition key and `ALL` projection
    - Table name driven by `customers_table_name` Terraform variable
    - _Requirements: 8.1, 8.2_

  - [x] 6.2 Define Cognito User Pool and App Client resources
    - `aws_cognito_user_pool` with password policy: minimum length 8, require uppercase, lowercase, digits, and symbols
    - `aws_cognito_user_pool_client` without a client secret
    - _Requirements: 1.6, 8.1_

  - [x] 6.3 Define IAM roles and least-privilege policies for Lambda functions
    - `aws_iam_role` for the Authorizer Lambda with basic Lambda execution trust policy
    - `aws_iam_role` for the Customers Lambda with basic Lambda execution trust policy
    - `aws_iam_role_policy` for Customers Lambda allowing only `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:DeleteItem`, and `dynamodb:Scan` on the specific DynamoDB table ARN — no other DynamoDB actions
    - _Requirements: 8.1, 8.5_

  - [x] 6.4 Define Lambda function resources and API Gateway REST API
    - `aws_lambda_function` for Authorizer and Customers Lambdas with environment variable blocks for `TABLE_NAME`, `COGNITO_USER_POOL_ID`, `COGNITO_REGION`, `COGNITO_APP_CLIENT_ID`
    - `aws_api_gateway_rest_api` (REGIONAL endpoint type) with resources `/customers` and `/customers/{customer_id}`
    - Attach TOKEN authorizer (`aws_api_gateway_authorizer`) to all methods with 300-second TTL cache
    - Configure Lambda proxy integrations for all methods
    - `aws_api_gateway_deployment` and `aws_api_gateway_stage` with HTTPS enforcement
    - CloudWatch access logging for the stage (production only, using `environment` variable conditional)
    - _Requirements: 7.1, 7.2, 7.3, 7.5, 8.1_

  - [x] 6.5 Add `infra/outputs.tf` with key output values and `infra/envs/prod.tfvars`
    - Output `api_invoke_url`, `cognito_user_pool_id`, `cognito_app_client_id`, `dynamodb_table_name`
    - Create `infra/envs/prod.tfvars` with production-appropriate variable values (mirroring `dev.tfvars` structure)
    - Confirm all provider versions are pinned in `infra/versions.tf`
    - _Requirements: 8.2, 8.3_

- [x] 7. Checkpoint — Validate Terraform configuration
  - Run `terraform init` and `terraform validate` in `infra/`; ensure exit code 0 and zero error diagnostics.
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Add integration tests and wire everything together
  - [x] 8.1 Create `tests/unit/conftest.py` and install test dependencies
    - Add `pytest`, `hypothesis`, `moto[dynamodb]`, `pytest-mock` to `tests/` requirements or `pyproject.toml`
    - Add `conftest.py` with shared fixtures: mocked DynamoDB table, sample valid customer body, sample JWT event
    - Ensure existing `tests/unit/__init__.py` and `tests/integration/__init__.py` are in place
    - _Requirements: (testing infrastructure)_

  - [x] 8.2 Create `tests/integration/test_api_integration.py`
    - Write example-based integration tests (not property-based) for: unauthenticated request → 401; full CRUD lifecycle with a real JWT; HTTPS-only verification
    - Include a conditional test for CloudWatch access log entry presence (production environment only)
    - Tests should read `API_BASE_URL`, `COGNITO_TOKEN`, and `ENVIRONMENT` from environment variables
    - _Requirements: 7.1, 7.2, 7.3, 7.5_

  - [x] 8.3 Update `src/customers/requirements.txt` and `src/authorizer/requirements.txt`
    - `src/authorizer/requirements.txt`: `boto3`, `python-jose[cryptography]`
    - `src/customers/requirements.txt`: `boto3`
    - Pin to exact versions compatible with the Lambda Python runtime
    - _Requirements: 8.1_

- [x] 9. Final checkpoint — Ensure all tests pass
  - Run `pytest tests/unit/` and confirm all tests pass.
  - Run `terraform validate` in `infra/` and confirm exit code 0.
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Property tests use Hypothesis with `settings(max_examples=100)` and are tagged with `# Feature: customer-management-platform, Property N: ...`
- Checkpoints ensure incremental validation between logical phases
- DynamoDB is mocked with `moto` in unit/property tests; integration tests require a deployed stack
- All source files must include a copyright header per project code standards
- The `build_response` helper is the single point of response construction — it must strip all internal error details before serializing

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "8.1"] },
    { "id": 2, "tasks": ["1.3", "2.1"] },
    { "id": 3, "tasks": ["2.2", "4.1", "6.1", "6.2"] },
    { "id": 4, "tasks": ["4.2", "4.3", "6.3"] },
    { "id": 5, "tasks": ["4.4", "4.5", "6.4"] },
    { "id": 6, "tasks": ["4.6", "4.7", "6.5"] },
    { "id": 7, "tasks": ["4.8", "4.9", "8.3"] },
    { "id": 8, "tasks": ["8.2"] }
  ]
}
```
