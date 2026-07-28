variable "aws_region" {
  description = "AWS region for all ERPX infrastructure."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment name (e.g. production, staging)."
  type        = string
  default     = "production"
}

variable "vpc_cidr" {
  description = "CIDR block for the ERPX VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "availability_zones" {
  description = "AZs to spread subnets across (at least 2 for RDS Multi-AZ)."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "db_instance_class" {
  description = "RDS instance class for the primary PostgreSQL database."
  type        = string
  default     = "db.t4g.medium"
}

variable "db_allocated_storage_gb" {
  description = "Initial RDS storage allocation in GB (autoscaling is enabled up to db_max_allocated_storage_gb)."
  type        = number
  default     = 50
}

variable "db_max_allocated_storage_gb" {
  type    = number
  default = 500
}

variable "db_name" {
  type    = string
  default = "erpx"
}

variable "db_username" {
  type    = string
  default = "erpx"
}

variable "db_password" {
  description = "RDS master password. Pass via TF_VAR_db_password or a tfvars file that is never committed — never hardcode this."
  type        = string
  sensitive   = true
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type."
  type        = string
  default     = "cache.t4g.small"
}

variable "enable_multi_az" {
  description = "Enable Multi-AZ for RDS. Should be true in production."
  type        = bool
  default     = true
}
