# Platform: applied only by GitHub Actions as role gha-deploy (see .github/workflows/infra.yml).
terraform {
  required_version = ">= 1.10"
  required_providers {
    aws       = { source = "hashicorp/aws", version = "~> 6.0" }
    snowflake = { source = "snowflakedb/snowflake", version = "~> 2.21" }
  }
  backend "s3" {
    bucket       = "fh26-tfstate-762197749808"
    key          = "platform/terraform.tfstate"
    region       = "us-east-2"
    use_lockfile = true
  }
}

provider "aws" {
  region = "us-east-2"
}

# Logs in as TF_DEPLOY using the ambient gha-deploy credentials (no secret).
provider "snowflake" {
  organization_name          = "RLQHFPF"
  account_name               = "AXC97788"
  user                       = "TF_DEPLOY"
  role                       = "ACCOUNTADMIN"
  authenticator              = "WORKLOAD_IDENTITY"
  workload_identity_provider = "AWS"
  preview_features_enabled = [
    "snowflake_storage_integration_aws_resource",
    "snowflake_stage_external_s3_resource",
    "snowflake_stage_internal_resource",
    "snowflake_file_format_csv_resource",
  ]
}

data "aws_caller_identity" "me" {}

locals {
  account_id          = data.aws_caller_identity.me.account_id
  github_sub_prefix   = "repo:Carlos310197@66190532/Factored-Hackathon-2026@1389485180" # immutable OIDC subject, see bootstrap
  serving_bucket      = "latam-bank-serving-${local.account_id}"
  serving_url         = "s3://${local.serving_bucket}/serving/"
  snowflake_role_name = "snowflake-serving"
  organizer_bucket    = "factored-datathon-2026-s3-157725502942-us-east-2-an"
}

output "serving_bucket" {
  value = aws_s3_bucket.serving.bucket
}

output "serving_role_arn" {
  value = aws_iam_role.snowflake_serving.arn
}

output "pipeline_runner_role_arn" {
  value = aws_iam_role.pipeline_runner.arn
}
