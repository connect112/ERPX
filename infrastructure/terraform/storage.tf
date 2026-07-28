# S3 replaces self-hosted MinIO in production — the storage package's
# S3-compatible client (packages/storage) talks to either identically.
resource "aws_s3_bucket" "erpx_storage" {
  bucket = "erpx-storage-${var.environment}"
  tags   = { Name = "erpx-storage" }
}

resource "aws_s3_bucket_versioning" "erpx_storage" {
  bucket = aws_s3_bucket.erpx_storage.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "erpx_storage" {
  bucket = aws_s3_bucket.erpx_storage.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "erpx_storage" {
  bucket                  = aws_s3_bucket.erpx_storage.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Container images referenced by infrastructure/kubernetes/*.yaml.
resource "aws_ecr_repository" "api" {
  name                 = "erpx-api"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "web" {
  name                 = "erpx-web"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "expire_untagged" {
  for_each   = { api = aws_ecr_repository.api.name, web = aws_ecr_repository.web.name }
  repository = each.value

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expire untagged images after 14 days"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = 14
      }
      action = { type = "expire" }
    }]
  })
}
