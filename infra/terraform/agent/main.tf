terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
  backend "s3" {
    bucket       = "fh26-tfstate-762197749808-use1"
    key          = "agent/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}

provider "aws" {
  region = "us-east-1"
}

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

data "aws_caller_identity" "current" {}

# Seeded by the data root; the deploy workflow writes the pushed image URI.
data "aws_ssm_parameter" "image" {
  name = data.terraform_remote_state.data.outputs.agent_image_parameter
}

data "aws_ecr_repository" "agent" {
  name = "lb-demo-agent"
}

data "aws_secretsmanager_secret" "jev" {
  name = "lb-demo/jev"
}

locals {
  account      = data.aws_caller_identity.current.account_id
  runtime_name = "lb_demo_agent"
  endpoint     = "live"
  audience     = "bankagent"
  issuer       = data.terraform_remote_state.identity.outputs.issuer
  image        = data.aws_ssm_parameter.image.value
  # extract uses Ministral: gpt-oss-20b failed too often on real messages.
  models              = { extract = "mistral.ministral-3-14b-instruct", compose = "openai.gpt-oss-120b" }
  resolver            = { artifact = "/app/src/bankagent/resolver/artifacts/v1", thresholds = "/app/src/bankagent/decisions/thresholds.v2.yaml" }
  bedrock_role_arn    = var.bedrock_role_arn
  bedrock_external_id = var.bedrock_external_id
}

# The AI Account role's trust policy must allow role/lb-demo-agent-exec with the external id.
variable "bedrock_role_arn" {
  description = "Role in the AI Account that the agent assumes for Bedrock calls."
  type        = string
}

variable "bedrock_external_id" {
  description = "External id the AI Account role's trust policy requires."
  type        = string
  sensitive   = true
}
