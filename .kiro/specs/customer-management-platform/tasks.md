# Implementation Plan: Customer Management Platform

## Overview

Implement a serverless customer management REST API on AWS using Python Lambda functions, API Gateway, DynamoDB, and Cognito. All infrastructure is managed by Terraform. The implementation proceeds in five phases: project scaffolding → Authorizer Lambda → Customer Lambda (CRUD + validation) → Terraform infrastructure → test suite.

## Tasks

- [ ] 1. Scaffold project structure and shared utilities
  - [ ] 1.1 Create directory structure and copyright-bearing placeholder files
    - Create `src/authorizer/`, `src/customers/`, `tests/unit/events/`, `tests/integration/`, `infra/envs/` directories
    - Add copyright header stub to every new Python file per code standards
    - Create `src/authorizer/requirements.txt` with `python-jose[cryptography]==3.3.0` and `boto3`
    - Create `src/customers/requirements.txt` with `boto3`
    - _Requirements: 8.1_

  - [ ] 1.2 Implement shared validation helpers in `src/customers/lambda_function.py`
    - Write `validate_customer_body(body)` that checks `name` (non-empty, ≤200 chars), `email` (RFC 5322 via `re`), `phone` (optional; digits/spaces/`-`/`+`/`()`, 7–20 chars), `address` (optional; non-empty, ≤500 chars)
    - Return a dict of `{field: reason}` for every failing field; return empty dict on success
    - Write `is_valid_uuid4(value)` helper for path parameter validation
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 1.3 Write property test for input validation (Property 3)
    - **Property 3: Input validation rejects all invalid customer records without writing to DynamoDB**
    - **Validates: Requirements 2.3, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**
    - Use Hypothesis `st.text()`, `st.emails()`, `st.from_regex()`, and boundary values
    - Confirm `validate_customer_body` returns at least one field error for every invalid input
    - Confirm no DynamoDB call is made (mock DynamoDB with `unittest.mock`)
    - Tag: `# Feature: customer-management-platform, Property 3`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [ ] 2. Implement Authorizer Lambda
  - [ ] 2.1 Write `src/authorizer/lambda_function.py` — JWT validation and IAM policy generation
    - Add module-level JWKS cache variable (populated on first warm invocation)
    - Implement `fetch_jwks(pool_id, region)` that retrieves and caches Cognito JWKS
    - Implement `lambda_handler(event, context)`: extract Bearer token → fetch JWKS (cached) → decode with `python-jose` verifying RS256 signature, `exp`, `iss`, and `aud` → return Allow or Deny IAM policy for `arn:aws:execute-api:*:*:*/customers*`
    - Read `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`, `AWS_REGION` from environment variables
    - On any failure return Deny policy; never raise an unhandled exception
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 2.2 Write property test for valid JWT always accepted (Property 1)
    - **Property 1: Valid JWT is always accepted**
    - **Validates: Requirements 1.1, 1.5**
    - Use `st.builds()` to generate valid JWT claims (varied `sub`, `iat`, future `exp`)
    - Sign tokens with a local RSA key; mock JWKS endpoint to return matching public key
    - Assert returned policy contains `Effect: Allow`
    - Tag: `# Feature: customer-management-platform, Property 1`
    - _Requirements: 1.1, 1.5_

  - [ ]* 2.3 Write property test for invalid JWT always rejected (Property 2)
    - **Property 2: Invalid JWT is always rejected**
    - **Validates: Requirements 1.2, 1.3, 1.4**
    - Use `st.text()` and `st.builds()` with tampered fields: past `exp`, wrong `iss`, wrong `aud`, bad signature key
    - Assert returned policy contains `Effect: Deny`
    - Tag: `# Feature: customer-management-platform, Property 2`
    - _Requirements: 1.2, 1.3, 1.4_

  - [ ]* 2.4 Write unit tests for Authorizer Lambda
    - Test: valid token → Allow policy
    - Test: expired token → Deny policy
    - Test: missing Authorization header → Deny policy
    - Test: wrong audience → Deny policy
    - Test: wrong issuer → Deny policy
    - Test: JWKS cache is reused on second invocation (no second HTTP call)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ] 3. Checkpoint — Authorizer tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement Customer Lambda — Create and Retrieve
  - [ ] 4.1 Implement route dispatcher and `create_customer` handler
    - Write `lambda_handler(event, context)` that dispatches on `httpMethod` + `resource` to the correct handler function
    - Write `create_customer(event)`: parse + validate body → query `email-index` GSI for uniqueness → `PutItem` to DynamoDB → return HTTP 201 with the new record including system-generated `customer_id` (UUID v4) and `created_at` (ISO 8601 UTC)
    - Return HTTP 400 for validation errors (all failing fields listed), HTTP 409 for duplicate email, HTTP 500 for DynamoDB write failure
    - Never include stack traces, ARNs, or raw AWS error messages in responses
    - Read `CUSTOMERS_TABLE_NAME` and `EMAIL_INDEX_NAME` from environment variables
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 7.4_

  - [ ]* 4.2 Write property test for create–retrieve round trip (Property 4)
    - **Property 4: Create–Retrieve round trip preserves all fields**
    - **Validates: Requirements 2.1, 2.2, 2.5, 3.1**
    - Use `st.builds(ValidCustomerRecord)` with `moto` mocking DynamoDB
    - Assert GET response `name`, `email`, `phone`, `address` match POST body exactly
    - Assert `customer_id` is a valid UUID v4 and `created_at` is ISO 8601 UTC; `updated_at` absent
    - Tag: `# Feature: customer-management-platform, Property 4`
    - _Requirements: 2.1, 2.2, 2.5, 3.1_

  - [ ] 4.3 Implement `get_customer` and `list_customers` handlers
    - Write `get_customer(event)`: validate path param UUID → `GetItem` → return HTTP 200 with full record or HTTP 404; return HTTP 400 for malformed UUID; return HTTP 503 for DynamoDB read failure
    - Write `list_customers(event)`: `Scan` with `Limit=100`; accept `nextToken` query param (base64-decoded `ExclusiveStartKey`); return `{"customers": [...], "nextToken": "..."|null}`; return HTTP 503 for DynamoDB failure
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 5.4_

  - [ ]* 4.4 Write property test for non-existent customer_id returns 404 (Property 8)
    - **Property 8: Non-existent customer_id returns HTTP 404 for GET, PUT, and DELETE**
    - **Validates: Requirements 3.2, 4.2, 5.2**
    - Use `st.uuids()` with `moto` (empty table)
    - Assert GET, PUT, DELETE all return HTTP 404
    - Tag: `# Feature: customer-management-platform, Property 8`
    - _Requirements: 3.2, 4.2, 5.2_

  - [ ]* 4.5 Write property test for malformed customer_id returns 400 (Property 9)
    - **Property 9: Malformed customer_id returns HTTP 400**
    - **Validates: Requirements 5.4**
    - Use `st.text()` filtered to exclude valid UUID v4 format
    - Assert GET, PUT, DELETE all return HTTP 400
    - Tag: `# Feature: customer-management-platform, Property 9`
    - _Requirements: 5.4_

  - [ ]* 4.6 Write property test for list pagination (Property 10)
    - **Property 10: List endpoint returns at most 100 records and provides nextToken when more exist**
    - **Validates: Requirements 3.3, 3.5**
    - Use `st.integers(min_value=0, max_value=150)` to seed the mocked DynamoDB table
    - Assert response contains ≤100 records; when N > 100, `nextToken` is non-null
    - Tag: `# Feature: customer-management-platform, Property 10`
    - _Requirements: 3.3, 3.5_

  - [ ]* 4.7 Write unit tests for Create and Retrieve
    - Test POST with valid body → 201 + customer_id in body
    - Test POST with missing `name` → 400 with field error
    - Test POST with missing `email` → 400 with field error
    - Test POST with invalid email format → 400
    - Test POST with `name` at 200 chars → 201; at 201 chars → 400
    - Test POST with duplicate email → 409
    - Test POST with DynamoDB write failure → 500 (no customer_id in body)
    - Test GET existing id → 200 with all fields
    - Test GET non-existent id → 404
    - Test GET malformed id → 400
    - Test GET list (0, 100, 101 records) — verify nextToken behavior
    - Test GET with DynamoDB read failure → 503
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 5. Implement Customer Lambda — Update and Delete
  - [ ] 5.1 Implement `update_customer` handler
    - Write `update_customer(event)`: validate UUID path param → validate body → check existence (`GetItem`) → query `email-index` GSI for uniqueness (skip 409 if returned `customer_id` matches current) → `UpdateItem` preserving original `customer_id` and `created_at`; set `updated_at` to current ISO 8601 UTC → return HTTP 200 with full updated record
    - Return HTTP 400 for validation errors, HTTP 404 for missing record, HTTP 409 for duplicate email on different customer
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 7.4_

  - [ ]* 5.2 Write property test for update preserves immutable fields (Property 5)
    - **Property 5: Update preserves immutable fields and sets updated_at**
    - **Validates: Requirements 4.5, 4.6**
    - Use `st.builds(ValidCustomerRecord)`, `st.uuids()`, `st.datetimes()` to inject arbitrary values for `customer_id` and `created_at` in the PUT body
    - Assert stored `customer_id` and `created_at` are unchanged; `updated_at` is a new non-empty ISO 8601 UTC string
    - Tag: `# Feature: customer-management-platform, Property 5`
    - _Requirements: 4.5, 4.6_

  - [ ]* 5.3 Write property test for email uniqueness (Property 6)
    - **Property 6: Email uniqueness is enforced across all customer records**
    - **Validates: Requirements 2.4, 4.4**
    - Use `st.emails()` and `st.builds(ValidCustomerRecord)` with `moto`
    - Assert second request (create or update) targeting a different `customer_id` with the same email returns HTTP 409
    - Assert DynamoDB contains at most one record with that email
    - Tag: `# Feature: customer-management-platform, Property 6`
    - _Requirements: 2.4, 4.4_

  - [ ] 5.4 Implement `delete_customer` handler
    - Write `delete_customer(event)`: validate UUID path param → `GetItem` to check existence → `DeleteItem` → return HTTP 200 with confirmation message containing `customer_id`
    - Return HTTP 400 for malformed UUID, HTTP 404 for non-existent record, HTTP 503 for DynamoDB failure
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 7.4_

  - [ ]* 5.5 Write property test for deleted records not retrievable (Property 7)
    - **Property 7: Deleted records are no longer retrievable**
    - **Validates: Requirements 5.1, 3.2**
    - Use `st.builds(ValidCustomerRecord)` with `moto`
    - Assert GET for deleted `customer_id` returns HTTP 404 with no customer data fields
    - Tag: `# Feature: customer-management-platform, Property 7`
    - _Requirements: 5.1, 3.2_

  - [ ]* 5.6 Write unit tests for Update and Delete
    - Test PUT valid body + existing id → 200 with updated record
    - Test PUT non-existent id → 404
    - Test PUT missing required field → 400
    - Test PUT duplicate email on different customer → 409
    - Test PUT with values for `customer_id` and `created_at` in body — assert originals preserved
    - Test PUT `updated_at` is set and differs from `created_at`
    - Test DELETE existing id → 200 with confirmation
    - Test DELETE non-existent id → 404
    - Test DELETE malformed id → 400
    - Test DELETE with DynamoDB failure → 503
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.1, 5.2, 5.3, 5.4_

  - [ ]* 5.7 Write property test for error responses sanitized (Property 11)
    - **Property 11: Error responses never expose internal details**
    - **Validates: Requirements 7.4**
    - Inject `ClientError`, `generic Exception`, and `ValidationError` via `unittest.mock`
    - Assert response body contains none of: stack traces, DynamoDB error codes, AWS ARNs, raw exception messages
    - Tag: `# Feature: customer-management-platform, Property 11`
    - _Requirements: 7.4_

- [ ] 6. Checkpoint — all Lambda unit and property tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Write Terraform infrastructure
  - [ ] 7.1 Create `infra/versions.tf` and `infra/providers.tf`
    - Pin `hashicorp/aws` provider version in `versions.tf`
    - Configure `aws` provider with `region` variable in `providers.tf`
    - _Requirements: 8.3_

  - [ ] 7.2 Create `infra/variables.tf` and environment tfvars
    - Declare variables: `environment`, `aws_region`, `cognito_user_pool_id`, `cognito_app_client_id`, `customers_table_name`, `email_index_name`
    - Populate `infra/envs/dev.tfvars` and `infra/envs/prod.tfvars` with environment-specific values
    - _Requirements: 8.2_

  - [ ] 7.3 Create `infra/main.tf` — DynamoDB and Cognito resources
    - Define `aws_dynamodb_table` with `PAY_PER_REQUEST` billing, partition key `customer_id` (S), and GSI `email-index` (partition key `email` (S), `KEYS_ONLY` projection)
    - Define `aws_cognito_user_pool` with password policy: min length 8, require uppercase, lowercase, digit, special char
    - Define `aws_cognito_user_pool_client` with no client secret
    - _Requirements: 8.1, 1.6_

  - [ ] 7.4 Create `infra/main.tf` — Lambda and IAM resources
    - Define `aws_iam_role` + `aws_iam_role_policy` for Authorizer Lambda: allow `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
    - Define `aws_iam_role` + `aws_iam_role_policy` for Customer Lambda: allow only `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:DeleteItem`, `dynamodb:Scan`, `dynamodb:Query` on the specific table and GSI ARNs; allow CloudWatch log actions
    - Define `aws_lambda_function` for Authorizer and Customer Lambdas with Python 3.12 runtime, correct handler paths, and environment variables
    - _Requirements: 8.1, 8.5_

  - [ ] 7.5 Create `infra/main.tf` — API Gateway resources
    - Define `aws_api_gateway_rest_api`, `/customers` resource, `{customer_id}` child resource
    - Define methods `POST GET` on `/customers` and `GET PUT DELETE` on `/customers/{customer_id}`, all using the Lambda Authorizer
    - Define `aws_api_gateway_authorizer` (TOKEN type) referencing the Authorizer Lambda
    - Define `aws_api_gateway_deployment` and `aws_api_gateway_stage` (`v1`)
    - Enable access logging on the stage for production environment (conditional on `environment == "prod"`); log format includes `requestId`, `httpMethod`, `resourcePath`, `status`, `requestTime`
    - _Requirements: 8.1, 7.1, 7.2, 7.3, 7.5_

  - [ ] 7.6 Create `infra/outputs.tf`
    - Output `api_base_url`, `cognito_user_pool_id`, `cognito_app_client_id`, `customers_table_name`
    - _Requirements: 8.1_

- [ ] 8. Checkpoint — `terraform plan` exits with code 0 and zero error diagnostics
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Integration wiring and final validation
  - [ ] 9.1 Wire Lambda environment variables to Terraform outputs
    - Ensure Authorizer Lambda env vars `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`, `AWS_REGION` reference the corresponding Terraform resources/variables
    - Ensure Customer Lambda env vars `CUSTOMERS_TABLE_NAME`, `EMAIL_INDEX_NAME` reference the DynamoDB table name and GSI name variables
    - _Requirements: 8.1, 8.2_

  - [ ]* 9.2 Write integration tests
    - Test end-to-end JWT flow: obtain token from Cognito, call POST /customers, receive 201
    - Test full CRUD lifecycle against real DynamoDB table
    - Test 401 response for requests without a token
    - Read connection details from `API_BASE_URL`, `COGNITO_CLIENT_ID`, `COGNITO_USER_POOL_ID`, `TEST_USERNAME`, `TEST_PASSWORD` environment variables
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 7.2_

- [ ] 10. Final checkpoint — Ensure all tests pass
  - Ensure all unit, property, and integration tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP delivery
- All Python source files must include a copyright header per code standards
- Property tests use Hypothesis with `@settings(max_examples=100)` and `moto` for DynamoDB mocking
- Unit tests use `pytest` with `moto` or `unittest.mock` for AWS service mocking
- Integration tests require a deployed dev stack and the env vars listed in task 9.2
- Each task references specific requirements for full traceability

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "7.1", "7.2"] },
    { "id": 2, "tasks": ["1.3", "2.1", "7.3"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4", "4.1", "7.4"] },
    { "id": 4, "tasks": ["4.2", "4.3", "7.5", "7.6"] },
    { "id": 5, "tasks": ["4.4", "4.5", "4.6", "4.7", "5.1"] },
    { "id": 6, "tasks": ["5.2", "5.3", "5.4"] },
    { "id": 7, "tasks": ["5.5", "5.6", "5.7", "9.1"] },
    { "id": 8, "tasks": ["9.2"] }
  ]
}
```
