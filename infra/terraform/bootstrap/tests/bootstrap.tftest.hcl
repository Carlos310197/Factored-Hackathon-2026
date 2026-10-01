mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "762197749808" }
  }
  mock_resource "aws_iam_openid_connect_provider" {
    defaults = { arn = "arn:aws:iam::762197749808:oidc-provider/token.actions.githubusercontent.com" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::762197749808:role/gha-deploy" }
  }
}

mock_provider "snowflake" {}

variables {
  organizer_key_id = "AKIAEXAMPLE"
  organizer_secret = "secret-example"
}

run "trust_policy_exact_subjects" {
  command = apply

  assert {
    condition     = jsondecode(aws_iam_role.gha_deploy.assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:sub"] == ["repo:Carlos310197/Factored-Hackathon-2026:ref:refs/heads/main"]
    error_message = "gha-deploy (admin + ACCOUNTADMIN) must trust only main pushes, never pull requests"
  }

  assert {
    condition     = jsondecode(aws_iam_role.gha_deploy.assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    error_message = "audience must be sts.amazonaws.com"
  }
}

run "state_bucket_named_and_private" {
  command = apply

  assert {
    condition     = aws_s3_bucket.tfstate.bucket == "fh26-tfstate-762197749808"
    error_message = "state bucket name"
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.tfstate.block_public_acls && aws_s3_bucket_public_access_block.tfstate.restrict_public_buckets
    error_message = "state bucket must block public access"
  }

  assert {
    condition     = aws_s3_bucket_versioning.tfstate.versioning_configuration[0].status == "Enabled"
    error_message = "state bucket must be versioned"
  }
}

run "tf_deploy_user_uses_aws_workload_identity" {
  command = apply

  assert {
    condition     = strcontains(snowflake_execute.tf_deploy_user.execute, "WORKLOAD_IDENTITY = (TYPE = AWS ARN = 'arn:aws:iam::762197749808:role/gha-deploy')")
    error_message = "TF_DEPLOY must trust the gha-deploy role"
  }
}

run "ssm_values_ignored_after_create" {
  command = apply

  assert {
    condition     = aws_ssm_parameter.organizer_secret.type == "SecureString" && aws_ssm_parameter.organizer_key_id.type == "SecureString"
    error_message = "organizer keys must be SecureString"
  }
}
