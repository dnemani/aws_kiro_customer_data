# Project Structure

Based on [AWS Prescriptive Guidance for Terraform](https://docs.aws.amazon.com/prescriptive-guidance/latest/terraform-aws-provider-best-practices/structure.html):

project-root/
├── src/
│   ├── authorizer/
│   │   ├── lambda_function.py
│   │   └── requirements.txt
│   └── users/
│       ├── lambda_function.py
│       └── requirements.txt
├── tests/
│   ├── unit/
│   │   └── events/
│   └── integration/
├── infra/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── providers.tf
│   ├── versions.tf
│   ├── terraform.tfvars
│   └── envs/
│       ├── dev.tfvars
│       └── prod.tfvars
└── README.md

## Conventions

- Lambda functions under `src/`, entry point `lambda_function.py`
- Terraform in `infra/` with standard file separation
- Environment-specific tfvars in `infra/envs/`