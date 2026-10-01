# Bootstrap: the trust chain CI uses. Applied once from a laptop via ./apply.sh, never from CI.
terraform {
  required_version = ">= 1.10"
  required_providers {
    aws       = { source = "hashicorp/aws", version = "~> 6.0" }
    snowflake = { source = "snowflakedb/snowflake", version = "~> 2.21" }
  }
}

# The repo uses GitHub's immutable OIDC subject: owner@owner_id/repo@repo_id
# (gh api repos/<owner>/<repo>/actions/oidc/customization/sub -> sub_claim_prefix).
variable "github_sub_prefix" {
  type    = string
  default = "repo:Carlos310197@66190532/Factored-Hackathon-2026@1389485180"
}

variable "organizer_key_id" {
  type      = string
  sensitive = true
}

variable "organizer_secret" {
  type      = string
  sensitive = true
}

provider "aws" {
  region = "us-east-1"
}

# Password comes from SNOWFLAKE_PASSWORD (apply.sh reads it from the snow CLI config).
provider "snowflake" {
  organization_name = "RLQHFPF"
  account_name      = "AXC97788"
  user              = "ANDRESZC"
  role              = "ACCOUNTADMIN"
}

data "aws_caller_identity" "me" {}

locals {
  account_id   = data.aws_caller_identity.me.account_id
  gha_subjects = ["${var.github_sub_prefix}:ref:refs/heads/main"]
}

# --- Terraform state ---
resource "aws_s3_bucket" "tfstate" {
  bucket        = "fh26-tfstate-${local.account_id}-use1" # -use1: S3 kept the old name pinned to us-east-2 after deletion
  force_destroy = true # region move 2026-10-01; state is backed up and re-uploaded by hand-off steps
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- GitHub Actions -> AWS ---
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

resource "aws_iam_role" "gha_deploy" {
  name = "gha-deploy"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRoleWithWebIdentity"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = local.gha_subjects
        }
      }
    }]
  })
}

# Admin, but reachable only from pushes to main (PR jobs get no cloud credentials).
resource "aws_iam_role_policy_attachment" "gha_deploy_admin" {
  role       = aws_iam_role.gha_deploy.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

# --- AWS role -> Snowflake (workload identity, no stored secret) ---
resource "snowflake_execute" "tf_deploy_user" {
  execute = "CREATE USER TF_DEPLOY TYPE = SERVICE WORKLOAD_IDENTITY = (TYPE = AWS ARN = '${aws_iam_role.gha_deploy.arn}') DEFAULT_ROLE = ACCOUNTADMIN"
  revert  = "DROP USER TF_DEPLOY"
}

# Storage integrations need ACCOUNTADMIN.
resource "snowflake_execute" "tf_deploy_grant" {
  execute    = "GRANT ROLE ACCOUNTADMIN TO USER TF_DEPLOY"
  revert     = "REVOKE ROLE ACCOUNTADMIN FROM USER TF_DEPLOY"
  depends_on = [snowflake_execute.tf_deploy_user]
}

# --- Organizer keys: from local .env once; CI reads them, never sets them ---
resource "aws_ssm_parameter" "organizer_key_id" {
  name  = "/fh26/organizer/aws_key_id"
  type  = "SecureString"
  value = var.organizer_key_id
  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "organizer_secret" {
  name  = "/fh26/organizer/aws_secret"
  type  = "SecureString"
  value = var.organizer_secret
  lifecycle {
    ignore_changes = [value]
  }
}

output "gha_deploy_role_arn" {
  value = aws_iam_role.gha_deploy.arn
}

output "state_bucket" {
  value = aws_s3_bucket.tfstate.bucket
}
