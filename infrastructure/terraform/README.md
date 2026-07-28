# ERPX Terraform (AWS)

Provisions the **stateful foundation** ERPX's Kubernetes manifests
(`infrastructure/kubernetes`) assume already exists: VPC, RDS Postgres,
ElastiCache Redis, an S3 bucket for object storage, and ECR repositories
for the API and web container images. It does **not** provision EKS or
ECS itself — pick one based on your team's operational preference and
add it as a separate `.tf` file; the VPC/subnets/security groups here
are already shaped for either (private subnets for compute, an `app`
security group to attach to node groups or task ENIs).

## Prerequisites

- An S3 bucket and DynamoDB table for Terraform state locking (referenced
  in `versions.tf`'s `backend "s3"` block) — create these once, by hand
  or in a separate bootstrap `.tf`, since this config can't provision
  the backend it depends on.
- AWS credentials with permission to create VPC/RDS/ElastiCache/S3/ECR
  resources.

## Usage

```bash
terraform init
terraform plan -var="db_password=$(openssl rand -base64 24)"
terraform apply -var="db_password=..."
```

Never hardcode `db_password` into a `.tfvars` file that gets committed —
pass it via `TF_VAR_db_password` in CI, or from a secrets manager.

## What this does NOT cover

- Compute (EKS/ECS) — see the note above.
- DNS/ACM certificates for the domains referenced in
  `infrastructure/kubernetes/ingress.yaml`.
- IAM roles for CI/CD to push to ECR / deploy to the cluster.
- Elasticsearch — run as a managed OpenSearch/Elastic Cloud instance;
  add an `aws_opensearch_domain` resource here if going that route.
