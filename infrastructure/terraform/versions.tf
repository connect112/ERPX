terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state is required for a team-shared setup — an S3 bucket +
  # DynamoDB lock table created out-of-band (chicken-and-egg: this
  # backend can't provision the bucket it depends on). Fill in the
  # bucket name and re-run `terraform init` once that bucket exists.
  backend "s3" {
    bucket         = "erpx-terraform-state"
    key            = "erpx/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "erpx-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "ERPX"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
