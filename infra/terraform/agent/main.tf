# Agent: AgentCore Runtime (container from /fh26/agent/image) with a custom JWT authorizer, and the `live` endpoint.
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

# The data root seeds a placeholder; the deploy workflow overwrites it with the pushed image URI.
data "aws_ssm_parameter" "image" {
  name = data.terraform_remote_state.data.outputs.agent_image_parameter
}

data "aws_ecr_repository" "agent" {
  name = "lb-demo-agent"
}

# Secret container comes from bootstrap; only its ARN is needed.
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
  # gpt-oss on the Bedrock Mantle endpoint (Architecture Decisions 2026-10-05: LLM model defaults).
  models = { extract = "openai.gpt-oss-20b", compose = "openai.gpt-oss-120b" }
  # Every Bedrock call runs as this role in account 040684487035 (full model access; this account's is limited).
  # Its trust policy must allow role/lb-demo-agent-exec with this external id.
  bedrock_role_arn    = "arn:aws:iam::040684487035:role/argos-bedrock-role"
  bedrock_external_id = "fh26-7c1e9a52-3b4d-4f0e-9a8b-2d6c5e1f0a73"
}
