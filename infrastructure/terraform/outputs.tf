output "vpc_id" {
  value = aws_vpc.erpx.id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "app_security_group_id" {
  description = "Attach this to your EKS node group or ECS task ENIs so they can reach the database and Redis."
  value       = aws_security_group.app.id
}

output "database_endpoint" {
  value     = aws_db_instance.erpx.endpoint
  sensitive = true
}

output "redis_primary_endpoint" {
  value = aws_elasticache_replication_group.erpx.primary_endpoint_address
}

output "s3_bucket_name" {
  value = aws_s3_bucket.erpx_storage.bucket
}

output "ecr_api_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "ecr_web_repository_url" {
  value = aws_ecr_repository.web.repository_url
}
