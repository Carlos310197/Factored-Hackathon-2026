locals {
  demo_users_key = "identity/demo_users.yaml"
}

resource "aws_cloudwatch_log_group" "identity" {
  name              = "/aws/lambda/lb-demo-identity"
  retention_in_days = 30
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "identity" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.identity.arn}:*"]
  }
  statement {
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
    resources = ["*"]
  }
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [data.aws_secretsmanager_secret.signing_key.arn]
  }
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${data.terraform_remote_state.data.outputs.serving_bucket_arn}/${local.demo_users_key}"]
  }
}

resource "aws_iam_role" "identity" {
  name               = "lb-demo-identity"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

resource "aws_iam_role_policy" "identity" {
  name   = "identity"
  role   = aws_iam_role.identity.id
  policy = data.aws_iam_policy_document.identity.json
}

resource "aws_lambda_function" "identity" {
  function_name = "lb-demo-identity"
  role          = aws_iam_role.identity.arn
  package_type  = "Image"
  image_uri     = data.aws_ssm_parameter.image.value
  architectures = ["arm64"]
  memory_size   = 512
  timeout       = 10
  # ponytail: login tickets live in process memory, so login and OTP must reach the same container. One container
  # keeps them together; a busy minute can throttle. Upgrade path: tickets in DynamoDB, then drop this.
  reserved_concurrent_executions = 1

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      IDP_ISSUER            = aws_apigatewayv2_api.this.api_endpoint
      IDP_AUDIENCE          = "bankagent"
      IDP_KID               = "lb-demo-1"
      IDP_SIGNING_SECRET_ID = "lb-demo/idp-signing-key"
      DEMO_USERS_S3_URI     = "s3://${data.terraform_remote_state.data.outputs.serving_bucket}/${local.demo_users_key}"
      IDP_DEMO_MODE         = "1"
    }
  }

  depends_on = [aws_cloudwatch_log_group.identity, aws_iam_role_policy.identity]
}
