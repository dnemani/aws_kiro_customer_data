# Requirements Document

## Introduction

AnyCompany requires a serverless customer management platform to consolidate fragmented customer data currently spread across spreadsheets and legacy systems. The MVP delivers a secure REST API backed by AWS Lambda and API Gateway, with Cognito-based user authentication and full CRUD operations for customer records stored in DynamoDB. The platform provides customer service representatives, sales team members, and internal applications with a single, authoritative source of customer information.

## Out of Scope for MVP

- Password reset / self-service account recovery

## Glossary

- **API**: The REST API exposed via AWS API Gateway that handles all customer management operations
- **Authorizer**: The AWS Lambda function that validates JWT tokens issued by Cognito before permitting access to protected endpoints
- **Cognito**: AWS Cognito User Pool used for user identity management and JWT token issuance
- **Customer**: A record representing an individual or organization whose data is managed by the platform
- **Customer_ID**: A system-generated unique identifier (UUID) assigned to each Customer at creation time
- **Customer_Record**: The full set of data fields associated with a Customer, including name, email, phone, and address
- **DynamoDB**: The AWS DynamoDB table used as the persistent data store for Customer records
- **JWT**: A JSON Web Token issued by Cognito and presented by callers to authenticate API requests
- **Lambda**: An AWS Lambda function that executes the business logic for customer CRUD operations
- **Requestor**: Any authenticated user or application that calls the API
- **System**: The complete customer management platform including API, Lambda functions, Authorizer, Cognito, and DynamoDB

---

## Requirements

### Requirement 1: User Authentication

**User Story:** As a customer service representative, I want to authenticate with my organizational credentials, so that I can securely access the customer management API.

#### Acceptance Criteria

1. WHEN a Requestor presents a valid JWT issued by Cognito, THE Authorizer SHALL permit the request to proceed to the target Lambda.
2. WHEN a Requestor presents an expired JWT, THE Authorizer SHALL reject the request with HTTP 401 Unauthorized.
3. WHEN a Requestor presents a malformed or missing JWT, THE Authorizer SHALL reject the request with HTTP 401 Unauthorized.
4. WHEN a Requestor presents a JWT signed with an unrecognized key, THE Authorizer SHALL reject the request with HTTP 401 Unauthorized.
5. THE Authorizer SHALL validate the JWT signature, expiration, issuer claim, and audience claim on every inbound request.
6. THE Cognito User Pool SHALL be configured to enforce a minimum password length of 8 characters containing at least one uppercase letter, one lowercase letter, one digit, and one special character.

---

### Requirement 2: Create Customer

**User Story:** As a customer service representative, I want to create a new customer record, so that new customers are captured in the centralized system.

#### Acceptance Criteria

1. WHEN a Requestor submits a POST request to `/customers` with a valid Customer_Record body, THE Lambda SHALL persist the record to DynamoDB and return HTTP 201 Created with the newly assigned Customer_ID.
2. THE Lambda SHALL generate a unique Customer_ID (UUID v4) for each new Customer at creation time.
3. WHEN a Requestor submits a POST request with a missing required field (name or email), an invalid email format, or a name exceeding 200 characters, THE Lambda SHALL return HTTP 400 Bad Request with an error message identifying the specific field and the reason for failure.
4. WHEN a Requestor submits a POST request with an email address that already exists in DynamoDB and all required fields are present and valid, THE Lambda SHALL return HTTP 409 Conflict with an error message indicating the email is already registered.
5. THE Lambda SHALL record the `created_at` timestamp (ISO 8601 UTC) on every new Customer_Record at creation time.
6. IF DynamoDB is unavailable or returns an error during a write operation, THEN THE Lambda SHALL return HTTP 500 Internal Server Error with an error message and SHALL NOT return a Customer_ID in the response body.

---

### Requirement 3: Retrieve Customer

**User Story:** As a customer service representative, I want to retrieve a customer record by ID, so that I can view accurate customer information quickly.

#### Acceptance Criteria

1. WHEN a Requestor submits a GET request to `/customers/{customer_id}` with a Customer_ID that is a valid UUID v4 string, THE Lambda SHALL return HTTP 200 OK with the complete Customer_Record containing all stored fields (customer_id, name, email, phone, address, created_at, updated_at).
2. WHEN a Requestor submits a GET request with a Customer_ID that does not exist in DynamoDB, THE Lambda SHALL return HTTP 404 Not Found with a response body containing an error message and no customer data fields.
3. WHEN a Requestor submits a GET request to `/customers`, THE Lambda SHALL return HTTP 200 OK with a list of up to 100 Customer records stored in DynamoDB.
4. IF DynamoDB is unavailable during a read operation, THEN THE Lambda SHALL return HTTP 503 Service Unavailable with a response body containing an error message indicating the service is temporarily unavailable.
5. WHEN the total number of Customer records in DynamoDB exceeds 100, THE Lambda SHALL support a `nextToken` query parameter to retrieve the next page of up to 100 records.

---

### Requirement 4: Update Customer

**User Story:** As a customer service representative, I want to update an existing customer record, so that customer information remains accurate over time.

#### Acceptance Criteria

1. WHEN a Requestor submits a PUT request to `/customers/{customer_id}` with a valid Customer_Record body and an existing Customer_ID, THE Lambda SHALL update the record in DynamoDB and return HTTP 200 OK with the updated Customer_Record including all server-generated fields such as `customer_id`, `created_at`, and `updated_at`.
2. WHEN a Requestor submits a PUT request with a Customer_ID that does not exist in DynamoDB, THE Lambda SHALL return HTTP 404 Not Found.
3. WHEN a Requestor submits a PUT request with a missing required field (name or email) or a malformed field value (e.g., invalid email format), THE Lambda SHALL return HTTP 400 Bad Request with an error message identifying the invalid or missing field by name.
4. WHEN a Requestor submits a PUT request to `/customers/{customer_id}` with an email address that already exists in DynamoDB for a different Customer_ID, THE Lambda SHALL return HTTP 409 Conflict with an error message indicating the email is already registered to another customer.
5. WHEN a Requestor submits a PUT request to `/customers/{customer_id}`, THE Lambda SHALL record the `updated_at` timestamp (ISO 8601 UTC) on the updated Customer_Record.
6. WHEN a Requestor submits a PUT request to `/customers/{customer_id}`, THE Lambda SHALL preserve the original `created_at` timestamp and `customer_id` regardless of any values for those fields supplied in the request body.

---

### Requirement 5: Delete Customer

**User Story:** As a customer service representative, I want to delete a customer record, so that outdated or erroneous entries can be removed from the system.

#### Acceptance Criteria

1. WHEN a Requestor submits a DELETE request to `/customers/{customer_id}` with an existing Customer_ID, THE Lambda SHALL remove the record from DynamoDB and return HTTP 200 OK with a response body containing a confirmation message identifying the deleted Customer_ID.
2. WHEN a Requestor submits a DELETE request with a Customer_ID that does not exist in DynamoDB, THE Lambda SHALL return HTTP 404 Not Found with a response body containing an error message and no confirmation message.
3. IF DynamoDB is unavailable during a delete operation, THEN THE Lambda SHALL return HTTP 503 Service Unavailable with a response body containing an error message indicating the service is temporarily unavailable.
4. WHEN a Requestor submits a DELETE request with a Customer_ID that is not a valid UUID v4 string, THE Lambda SHALL return HTTP 400 Bad Request with an error message identifying the malformed Customer_ID.

---

### Requirement 6: Data Validation

**User Story:** As a system integrator, I want all customer data to be validated before persistence, so that the DynamoDB table contains only well-formed records.

#### Acceptance Criteria

1. WHEN a Requestor submits a create or update request, THE Lambda SHALL validate that the `name` field is a non-empty string with a maximum length of 200 characters.
2. WHEN a Requestor submits a create or update request, THE Lambda SHALL validate that the `email` field conforms to RFC 5322 address format.
3. IF the `phone` field is present in the request body, THEN THE Lambda SHALL validate that it contains only digits, spaces, hyphens, plus signs, and parentheses, with a minimum length of 7 characters and a maximum length of 20 characters.
4. IF the `address` field is present in the request body, THEN THE Lambda SHALL validate that it is a non-empty string with a maximum length of 500 characters.
5. WHEN any validation rule is violated, THE Lambda SHALL return HTTP 400 Bad Request with an error message listing all failed fields and the reason for each failure, without writing any data to DynamoDB.
6. WHEN a Requestor submits a POST request to `/customers` without a `name` field or without an `email` field, THE Lambda SHALL return HTTP 400 Bad Request with an error message identifying each missing mandatory field.

---

### Requirement 7: API Security

**User Story:** As a security engineer, I want all API endpoints to be protected, so that only authenticated users can access customer data.

#### Acceptance Criteria

1. THE API SHALL require a JWT on every request to every `/customers` endpoint, where a valid JWT is defined as one that passes signature verification against the Cognito User Pool's JWKS endpoint, has not expired, and contains the expected issuer and audience claims.
2. IF a request to a `/customers` endpoint does not include a JWT that passes all validation checks in criterion 1, THEN THE API SHALL return HTTP 401 Unauthorized at the API Gateway level without invoking any Lambda function.
3. THE API SHALL enforce HTTPS for all inbound requests.
4. THE Lambda SHALL not include stack traces, DynamoDB error codes, internal resource ARNs, or raw exception messages in HTTP responses returned to the Requestor.
5. WHERE the deployment environment is production, THE System SHALL enable AWS API Gateway access logging to CloudWatch such that each log entry contains at minimum the request ID, HTTP method, resource path, response status code, and timestamp.

---

### Requirement 8: Infrastructure as Code

**User Story:** As a DevOps engineer, I want all infrastructure defined in Terraform, so that the environment can be reproduced consistently across dev and prod.

#### Acceptance Criteria

1. THE System SHALL define all AWS resources (Lambda, API Gateway, Cognito, DynamoDB, IAM roles) exclusively using Terraform configuration files located under `infra/`.
2. THE System SHALL separate environment-specific values into `infra/envs/dev.tfvars` and `infra/envs/prod.tfvars`.
3. THE System SHALL pin all Terraform provider versions in `infra/versions.tf`.
4. WHEN `terraform plan` is executed with no existing state file and no previously applied infrastructure, THE System SHALL produce output with exit code 0 and zero error diagnostics.
5. THE System SHALL grant each Lambda function an IAM role whose policy allows only the specific DynamoDB actions that Lambda explicitly invokes (e.g., the customer CRUD Lambda is allowed `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:DeleteItem`, and `dynamodb:Scan` and no other DynamoDB actions).
