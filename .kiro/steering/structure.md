# Project Structure

Layout informed by [AWS Prescriptive Guidance for Terraform](https://docs.aws.amazon.com/prescriptive-guidance/latest/terraform-aws-provider-best-practices/structure.html). The Terraform configuration is split into one file per logical concern rather than a single `main.tf`.

```
project-root/
├── src/
│   ├── authorizer/
│   │   ├── lambda_function.py       # JWT validation authorizer handler
│   │   ├── requirements.txt         # boto3, python-jose[cryptography]
│   │   └── lambda_authorizer.zip    # build artifact (produced by archive_file)
│   └── customers/
│       ├── lambda_function.py       # CRUD router + handlers
│       ├── utils.py                 # is_valid_uuid4, build_response,
│       │                            #   get_dynamodb_table, validate_customer_body
│       ├── requirements.txt         # boto3
│       └── lambda_customers.zip     # build artifact (produced by archive_file)
├── tests/
│   ├── requirements.txt             # pytest, hypothesis, moto[dynamodb], python-jose
│   ├── unit/
│   │   ├── conftest.py              # shared fixtures
│   │   ├── test_authorizer.py       # Properties 1, 2 + examples
│   │   ├── test_customers_validation.py  # Properties 5, 10 + boundaries
│   │   ├── test_customers_crud.py   # Properties 3,4,6,7,8,9,11 + examples
│   │   └── events/                  # static JSON event fixtures
│   └── integration/
│       └── test_api_integration.py  # runs against a deployed stack
├── infra/
│   ├── main.tf              # DynamoDB table (customer_records)
│   ├── cognito.tf           # Cognito user pool + app client
│   ├── iam.tf               # Lambda execution roles + least-privilege policies
│   ├── lambda.tf            # Lambda functions, permissions, archive_file zips
│   ├── api_gateway.tf       # REST API, resources, methods, integrations,
│   │                        #   TOKEN authorizer, deployment, stage, access logs
│   ├── backend.tf           # S3 remote-state backend block (config via -backend-config)
│   ├── providers.tf         # AWS provider configuration
│   ├── versions.tf          # pinned Terraform + provider versions
│   ├── variables.tf         # input variable declarations
│   ├── outputs.tf           # api_invoke_url, cognito_*, dynamodb_table_name
│   ├── deployer-policy.json           # full IAM policy for customer-platform-deployer
│   ├── deployer-policy-additions.json # historical additive policy fragments
│   └── envs/
│       ├── dev.tfvars              # dev variable values
│       ├── prod.tfvars             # prod variable values
│       ├── dev.s3.tfbackend        # dev remote-state backend config
│       └── prod.s3.tfbackend       # prod remote-state backend config
└── scripts/
    ├── bootstrap_backend.sh        # one-time: create S3 state bucket + DynamoDB lock table
    └── import_existing_dev.sh      # import pre-existing dev resources into TF state
```

## Conventions

- Lambda functions live under `src/<name>/`, entry point always `lambda_function.py`.
  Shared helpers for the customers Lambda live in `src/customers/utils.py`.
- Deployment zips (`*.zip`) are build artifacts produced by Terraform `archive_file`
  data sources — they are not hand-edited.
- Terraform lives in `infra/`, split one file per concern (see tree above). There is no
  monolithic `main.tf`; `main.tf` holds only the DynamoDB table.
- Environment-specific values live in `infra/envs/`:
  - `*.tfvars` — input variables (`terraform apply -var-file=envs/<env>.tfvars`)
  - `*.s3.tfbackend` — remote-state backend config (`terraform init -backend-config=envs/<env>.s3.tfbackend`)
- Remote state is stored in S3 with a DynamoDB lock table; see `infra/backend.tf` and
  `scripts/bootstrap_backend.sh`.
- The IAM policy the deploying user needs is version-controlled in
  `infra/deployer-policy.json` (kept in sync with what is attached to
  `customer-platform-deployer`).
- All source files include a copyright header.
