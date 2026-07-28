data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "erpx" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "erpx-vpc" }
}

resource "aws_internet_gateway" "erpx" {
  vpc_id = aws_vpc.erpx.id
  tags   = { Name = "erpx-igw" }
}

resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.erpx.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = { Name = "erpx-public-${var.availability_zones[count.index]}" }
}

resource "aws_subnet" "private" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.erpx.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 100)
  availability_zone = var.availability_zones[count.index]

  tags = { Name = "erpx-private-${var.availability_zones[count.index]}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.erpx.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.erpx.id
  }

  tags = { Name = "erpx-public-rt" }
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Private subnets (RDS, ElastiCache) have no route to the internet by
# design — the app tier reaches them over the VPC's internal network only.

resource "aws_security_group" "database" {
  name        = "erpx-database-sg"
  description = "Allow Postgres access from the app tier's security group only"
  vpc_id      = aws_vpc.erpx.id

  ingress {
    description     = "Postgres from app tier"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "erpx-database-sg" }
}

resource "aws_security_group" "redis" {
  name        = "erpx-redis-sg"
  description = "Allow Redis access from the app tier's security group only"
  vpc_id      = aws_vpc.erpx.id

  ingress {
    description     = "Redis from app tier"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "erpx-redis-sg" }
}

resource "aws_security_group" "app" {
  name        = "erpx-app-sg"
  description = "Security group for ERPX API/Celery/web workloads (EKS nodes or ECS tasks)"
  vpc_id      = aws_vpc.erpx.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "erpx-app-sg" }
}
