resource "aws_db_subnet_group" "erpx" {
  name       = "erpx-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id
  tags       = { Name = "erpx-db-subnet-group" }
}

resource "aws_db_instance" "erpx" {
  identifier     = "erpx-postgres"
  engine         = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage_gb
  max_allocated_storage = var.db_max_allocated_storage_gb
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.erpx.name
  vpc_security_group_ids = [aws_security_group.database.id]
  multi_az                = var.enable_multi_az
  publicly_accessible     = false

  backup_retention_period = 14
  backup_window           = "03:00-04:00"
  maintenance_window      = "mon:04:30-mon:05:30"

  deletion_protection      = var.environment == "production"
  skip_final_snapshot      = var.environment != "production"
  final_snapshot_identifier = var.environment == "production" ? "erpx-postgres-final-snapshot" : null

  performance_insights_enabled = true

  tags = { Name = "erpx-postgres" }
}

resource "aws_elasticache_subnet_group" "erpx" {
  name       = "erpx-redis-subnet-group"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_replication_group" "erpx" {
  replication_group_id = "erpx-redis"
  description           = "ERPX Celery broker/result-backend + caching"

  engine         = "redis"
  engine_version = "7.1"
  node_type      = var.redis_node_type

  num_cache_clusters         = var.enable_multi_az ? 2 : 1
  automatic_failover_enabled = var.enable_multi_az
  multi_az_enabled           = var.enable_multi_az

  subnet_group_name = aws_elasticache_subnet_group.erpx.name
  security_group_ids = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  tags = { Name = "erpx-redis" }
}
