# Technology Stack

## Infrastructure

- **IaC Tool**: Terraform
- **Cloud Provider**: AWS
- **Default Region**: us-east-1

## Runtime & Languages

- **Primary Language**: Python
- **Runtime Environment**: AWS Lambda

## Key AWS Services

- AWS Lambda (compute)
- API Gateway (REST API)
- Lambda Authorizer (custom authentication)

## Dependencies

### Authorizer Lambda
- `boto3` - AWS SDK for Python
- `python-jose` - JWT token handling
- `datetime` - date/time operations

## Common Commands

### Terraform Operations
terraform init
terraform plan
terraform apply
terraform destroy

### Testing
pytest tests/unit/
pytest tests/integration/
pytest tests/

## Code Standards

- All source files must include copyright header