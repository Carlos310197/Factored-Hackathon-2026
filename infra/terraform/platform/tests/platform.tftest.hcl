mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "762197749808" }
  }
  mock_data "aws_ssm_parameter" {
    defaults = { value = "mock-organizer-value" }
  }
  mock_data "aws_iam_openid_connect_provider" {
    defaults = { arn = "arn:aws:iam::762197749808:oidc-provider/token.actions.githubusercontent.com" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::762197749808:role/pipeline-runner" }
  }
}

mock_provider "snowflake" {
  mock_resource "snowflake_storage_integration_aws" {
    defaults = {
      describe_output = [{
        iam_user_arn = "arn:aws:iam::999999999999:user/snowflake-mock"
        external_id  = "MOCK_EXTERNAL_ID"
      }]
    }
  }
}

run "serving_role_trusts_integration" {
  command = apply

  assert {
    condition     = jsondecode(aws_iam_role.snowflake_serving.assume_role_policy).Statement[0].Principal.AWS == "arn:aws:iam::999999999999:user/snowflake-mock"
    error_message = "snowflake-serving must trust the integration's IAM user"
  }

  assert {
    condition     = jsondecode(aws_iam_role.snowflake_serving.assume_role_policy).Statement[0].Condition.StringEquals["sts:ExternalId"] == "MOCK_EXTERNAL_ID"
    error_message = "snowflake-serving must require the integration's external id"
  }

  assert {
    condition     = snowflake_storage_integration_aws.serving.storage_aws_role_arn == "arn:aws:iam::762197749808:role/snowflake-serving"
    error_message = "integration must point at the fixed role name"
  }
}

run "serving_bucket_scoped" {
  command = apply

  assert {
    condition     = aws_s3_bucket.serving.bucket == "latam-bank-serving-762197749808"
    error_message = "serving bucket name"
  }

  assert {
    condition     = toset(snowflake_storage_integration_aws.serving.storage_allowed_locations) == toset(["s3://latam-bank-serving-762197749808/serving/"])
    error_message = "integration limited to the serving/ prefix"
  }
}

run "serving_bucket_denies_plain_http" {
  command = apply

  assert {
    condition = anytrue([
      for st in jsondecode(aws_s3_bucket_policy.serving.policy).Statement :
      st.Effect == "Deny" && st.Condition.Bool["aws:SecureTransport"] == "false"
    ])
    error_message = "serving bucket must deny non-TLS requests"
  }
}

run "all_schemas_in_both_databases" {
  command = apply

  assert {
    condition     = length(snowflake_schema.s) == 8
    error_message = "4 schemas x 2 databases"
  }

  assert {
    condition     = contains(keys(snowflake_schema.s), "LATAM_FIXTURE.META") && contains(keys(snowflake_schema.s), "LATAM_BANK.RAW")
    error_message = "schema keys are DB.SCHEMA"
  }
}

run "pipeline_user_uses_aws_workload_identity" {
  command = apply

  assert {
    condition     = strcontains(snowflake_execute.pipeline_user.execute, "WORKLOAD_IDENTITY = (TYPE = AWS ARN = 'arn:aws:iam::762197749808:role/pipeline-runner')")
    error_message = "PIPELINE_SVC must trust its own role, not gha-deploy (one AWS identity per Snowflake user)"
  }

  assert {
    condition     = !strcontains(snowflake_execute.pipeline_user.execute, "gha-deploy")
    error_message = "gha-deploy is TF_DEPLOY's identity"
  }

  assert {
    condition     = jsondecode(aws_iam_role.pipeline_runner.assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:sub"] == ["repo:Carlos310197/Factored-Hackathon-2026:ref:refs/heads/main"]
    error_message = "pipeline-runner (PIPELINE_ROLE writes prod schemas) trusts only main pushes"
  }
}
