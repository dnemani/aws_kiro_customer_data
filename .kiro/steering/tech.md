# Technology Stack

## Infrastructure

- **IaC Tool**: Terraform (>= 1.5; pinned in `infra/versions.tf`)
- **Cloud Provider**: AWS
- **Default Region**: us-east-1
- **Remote State**: S3 backend (`customer-platform-tfstate-114943206720`) with a
  DynamoDB lock table (`customer_records_tflock`). Backend block in `infra/backend.tf`;
  per-environment config in `infra/envs/<env>.s3.tfbackend`.

## Runtime & Languages

- **Primary Language**: Python
- **Runtime Environment**: AWS Lambda

## Key AWS Services

- AWS Lambda (compute — `customers` CRUD + `authorizer`)
- API Gateway (REST API, REGIONAL, HTTPS-only, TOKEN authorizer)
- DynamoDB (`customer_records_<env>`, on-demand, `email-index` GSI)
- Cognito (user pool + app client, JWT issuance)
- IAM (least-privilege Lambda execution roles)
- CloudWatch Logs (Lambda logs always; API Gateway access logs in prod only)
- S3 + DynamoDB (Terraform remote state + locking)

## Dependencies

### Authorizer Lambda (`src/authorizer/requirements.txt`)
- `boto3` - AWS SDK for Python
- `python-jose[cryptography]` - JWT validation

### Customers Lambda (`src/customers/requirements.txt`)
- `boto3` - AWS SDK for Python

### Tests (`tests/requirements.txt`)
- `pytest` - test runner
- `hypothesis` - property-based testing (`max_examples=100`)
- `moto[dynamodb]` - in-memory DynamoDB mock for unit tests
- `python-jose[cryptography]` - used by authorizer tests

## Common Commands

### First-time backend setup (once per AWS account, admin creds)
```
./scripts/bootstrap_backend.sh
```

### Terraform Operations (per environment)
```
cd infra
terraform init -backend-config=envs/dev.s3.tfbackend          # prod: envs/prod.s3.tfbackend
terraform plan  -var-file=envs/dev.tfvars
terraform apply -var-file=envs/dev.tfvars
terraform destroy -var-file=envs/dev.tfvars
```
Use the `customer-platform` AWS profile (`AWS_PROFILE=customer-platform`).

### Importing pre-existing dev resources (idempotent)
```
AWS_PROFILE=customer-platform ./scripts/import_existing_dev.sh
```

### Testing
```
pytest tests/unit/          # unit + property tests (mocked, no AWS)
pytest tests/integration/   # requires deployed stack + env vars
pytest tests/
```

## Code Standards

- All source files must include a copyright header.
- All caller-facing error responses go through `build_response`, which strips stack
  traces, ARNs, and DynamoDB error codes.
