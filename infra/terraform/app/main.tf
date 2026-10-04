# App: the web UI (Next.js BFF) on ECS Fargate Spot. Applied only by GitHub Actions as gha-deploy.
# ponytail: no ALB until demo day (saves ~$16/mo); tasks get a public IP and the security group admits
# only the team's IPs. Demo day: add an ALB + HTTPS and switch to FARGATE (on-demand).
terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
  backend "s3" {
    bucket       = "fh26-tfstate-762197749808-use1"
    key          = "app/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}

provider "aws" {
  region = "us-east-1"
}

variable "allowed_cidrs" {
  description = "Team IPs allowed to reach the app (curl checkip.amazonaws.com)"
  type        = list(string)
  default     = ["181.67.2.219/32", "38.25.85.60/32"] # Andrés, Carlos
}

variable "image" {
  description = "Container image; a placeholder until web/ ships an image to ECR"
  type        = string
  default     = "public.ecr.aws/docker/library/node:22-alpine"
}

variable "command" {
  description = "Container command; only the placeholder needs one"
  type        = list(string)
  default     = ["node", "-e", "require('http').createServer((q,s)=>s.end('latam-bank web placeholder')).listen(3000)"]
}

data "aws_vpc" "default" {
  default = true
}

# Default VPC public subnets; us-east-1e historically lacks Fargate.
data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
  filter {
    name   = "availability-zone"
    values = ["us-east-1a", "us-east-1b", "us-east-1c", "us-east-1d", "us-east-1f"]
  }
}

output "cluster" {
  value = aws_ecs_cluster.main.name
}

output "service" {
  value = aws_ecs_service.web.name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.web.repository_url
}
