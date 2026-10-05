# App: the web UI (Next.js BFF) on ECS Fargate Spot behind a public ALB (stable URL). Applied only by GitHub Actions
# as gha-deploy. HTTP only: there is no domain, so no certificate (cookies are not Secure; disclosed in the README).
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

variable "image" {
  description = "Placeholder image for the first apply only; afterwards the SSM parameter /fh26/web/image (written by the deploy workflow) is the source of truth"
  type        = string
  default     = "public.ecr.aws/docker/library/node:22-alpine"
}

variable "command" {
  description = "Command override, applied only while the image is still the placeholder; the real image runs its own CMD"
  type        = list(string)
  default     = ["node", "-e", "require('http').createServer((q,s)=>s.end('latam-bank web placeholder')).listen(3000)"]
}

# Other roots' outputs (read-only).
data "terraform_remote_state" "data" {
  backend = "s3"
  config = {
    bucket = "fh26-tfstate-762197749808-use1"
    key    = "data/terraform.tfstate"
    region = "us-east-1"
  }
}

data "terraform_remote_state" "identity" {
  backend = "s3"
  config = {
    bucket = "fh26-tfstate-762197749808-use1"
    key    = "identity/terraform.tfstate"
    region = "us-east-1"
  }
}

# ponytail: needs the agent root (unit 83) applied first; it exports invoke_url.
data "terraform_remote_state" "agent" {
  backend = "s3"
  config = {
    bucket = "fh26-tfstate-762197749808-use1"
    key    = "agent/terraform.tfstate"
    region = "us-east-1"
  }
}

data "terraform_remote_state" "realtime" {
  backend = "s3"
  config = {
    bucket = "fh26-tfstate-762197749808-use1"
    key    = "realtime/terraform.tfstate"
    region = "us-east-1"
  }
}

# The image the service runs. Created with the placeholder; the deploy workflow overwrites it with
# <ecr_repository_url>:<git sha>, and ignore_changes keeps a later apply from rolling it back.
resource "aws_ssm_parameter" "web_image" {
  name  = "/fh26/web/image"
  type  = "String"
  value = var.image

  lifecycle {
    ignore_changes = [value]
  }
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

output "url" {
  description = "Stable public URL of the web app"
  value       = "http://${aws_lb.web.dns_name}"
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

output "task_role_arn" {
  value = aws_iam_role.task.arn
}

output "image_parameter" {
  value = aws_ssm_parameter.web_image.name
}

# NEXT_PUBLIC_* are inlined at build time: the deploy workflow passes this as a docker --build-arg.
output "events_http_domain" {
  value = data.terraform_remote_state.realtime.outputs.http_domain
}
