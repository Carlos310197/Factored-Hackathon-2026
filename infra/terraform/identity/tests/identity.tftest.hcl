mock_provider "aws" {
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
  mock_resource "aws_apigatewayv2_api" {
    defaults = {
      api_endpoint  = "https://abc123.execute-api.us-east-1.amazonaws.com"
      execution_arn = "arn:aws:execute-api:us-east-1:762197749808:abc123"
    }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::762197749808:role/lb-demo-identity" }
  }
  mock_resource "aws_cloudwatch_log_group" {
    defaults = { arn = "arn:aws:logs:us-east-1:762197749808:log-group:/aws/lambda/lb-demo-identity" }
  }
}

override_data {
  target = data.terraform_remote_state.data
  values = {
    outputs = {
      identity_image_parameter = "/fh26/identity/image"
      serving_bucket           = "latam-bank-serving-762197749808-use1"
      serving_bucket_arn       = "arn:aws:s3:::latam-bank-serving-762197749808-use1"
    }
  }
}

override_data {
  target = data.aws_ssm_parameter.image
  values = { value = "762197749808.dkr.ecr.us-east-1.amazonaws.com/lb-demo-identity:abc" }
}

override_data {
  target = data.aws_secretsmanager_secret.signing_key
  values = { arn = "arn:aws:secretsmanager:us-east-1:762197749808:secret:lb-demo/idp-signing-key-AbCdEf" }
}

run "lambda_is_arm64_image_with_idp_environment" {
  command = apply

  assert {
    condition     = aws_lambda_function.identity.package_type == "Image" && aws_lambda_function.identity.architectures == tolist(["arm64"]) && aws_lambda_function.identity.image_uri == "762197749808.dkr.ecr.us-east-1.amazonaws.com/lb-demo-identity:abc"
    error_message = "arm64 image from the parameter"
  }
  assert {
    condition     = aws_lambda_function.identity.memory_size == 512 && aws_lambda_function.identity.timeout == 10 && aws_lambda_function.identity.tracing_config[0].mode == "Active"
    error_message = "512 MB, 10 s, X-Ray active"
  }
  assert {
    condition = aws_lambda_function.identity.environment[0].variables == tomap({
      IDP_ISSUER            = "https://abc123.execute-api.us-east-1.amazonaws.com"
      IDP_AUDIENCE          = "bankagent"
      IDP_KID               = "lb-demo-1"
      IDP_SIGNING_SECRET_ID = "lb-demo/idp-signing-key"
      DEMO_USERS_S3_URI     = "s3://latam-bank-serving-762197749808-use1/identity/demo_users.yaml"
      IDP_DEMO_MODE         = "1"
    })
    error_message = "IdP environment (no secret values)"
  }
}

run "http_api_proxies_everything_and_is_throttled" {
  command = apply

  assert {
    condition     = aws_apigatewayv2_api.this.protocol_type == "HTTP" && aws_apigatewayv2_route.default.route_key == "$default"
    error_message = "single $default route"
  }
  assert {
    condition     = aws_apigatewayv2_integration.this.integration_type == "AWS_PROXY" && aws_apigatewayv2_integration.this.payload_format_version == "2.0"
    error_message = "AWS_PROXY payload 2.0"
  }
  assert {
    condition     = aws_apigatewayv2_stage.default.name == "$default" && aws_apigatewayv2_stage.default.auto_deploy && aws_apigatewayv2_stage.default.default_route_settings[0].throttling_rate_limit == 10 && aws_apigatewayv2_stage.default.default_route_settings[0].throttling_burst_limit == 20
    error_message = "auto-deploy stage throttled 10/s burst 20"
  }
  assert {
    condition     = aws_lambda_permission.api.source_arn == "arn:aws:execute-api:us-east-1:762197749808:abc123/*" && aws_lambda_permission.api.principal == "apigateway.amazonaws.com"
    error_message = "permission scoped to this API"
  }
}

run "lambda_reads_only_its_secret_and_the_identities_object" {
  command = apply

  assert {
    condition     = contains([for s in data.aws_iam_policy_document.identity.statement : s.resources if contains(s.actions, "secretsmanager:GetSecretValue")][0], "arn:aws:secretsmanager:us-east-1:762197749808:secret:lb-demo/idp-signing-key-AbCdEf")
    error_message = "only the signing secret"
  }
  assert {
    condition     = [for s in data.aws_iam_policy_document.identity.statement : s.resources if contains(s.actions, "s3:GetObject")][0] == toset(["arn:aws:s3:::latam-bank-serving-762197749808-use1/identity/demo_users.yaml"])
    error_message = "only the demo users object"
  }
}

run "logs_kept_30_days_and_issuer_output" {
  command = apply

  assert {
    condition     = aws_cloudwatch_log_group.identity.name == "/aws/lambda/lb-demo-identity" && aws_cloudwatch_log_group.identity.retention_in_days == 30
    error_message = "30-day log group"
  }
  assert {
    condition     = output.issuer == "https://abc123.execute-api.us-east-1.amazonaws.com" && output.jwks_url == "https://abc123.execute-api.us-east-1.amazonaws.com/jwks.json"
    error_message = "issuer without trailing slash, jwks_url"
  }
}
