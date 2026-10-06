# Browsers subscribe through the Lambda authorizer; only IAM publishes.
resource "aws_appsync_api" "this" {
  name = "lb-demo-realtime"

  event_config {
    auth_provider {
      auth_type = "AWS_IAM"
    }
    auth_provider {
      auth_type = "AWS_LAMBDA"
      lambda_authorizer_config {
        authorizer_uri                   = aws_lambda_function.authorizer.arn
        authorizer_result_ttl_in_seconds = 0
      }
    }
    connection_auth_mode {
      auth_type = "AWS_LAMBDA"
    }
    default_publish_auth_mode {
      auth_type = "AWS_IAM"
    }
    default_subscribe_auth_mode {
      auth_type = "AWS_LAMBDA"
    }
    # ALL can write customer message text to CloudWatch; use it only briefly for debugging.
    log_config {
      cloudwatch_logs_role_arn = aws_iam_role.appsync_logs.arn
      log_level                = var.appsync_log_level
    }
  }
}

resource "aws_appsync_channel_namespace" "this" {
  for_each = toset(["session", "queue", "trace"])

  api_id        = aws_appsync_api.this.api_id
  name          = each.key
  code_handlers = file("${path.module}/../../realtime/handlers/namespace.js")
}

resource "aws_lambda_permission" "appsync" {
  statement_id  = "AllowAppSyncEvents"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.authorizer.function_name
  principal     = "appsync.amazonaws.com"
  source_arn    = aws_appsync_api.this.api_arn
}

# The role policy uses a prefix wildcard: api_id is unknown until the API exists.
resource "aws_cloudwatch_log_group" "appsync" {
  name              = "/aws/appsync/apis/${aws_appsync_api.this.api_id}"
  retention_in_days = 30
}

data "aws_iam_policy_document" "appsync_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["appsync.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "appsync_logs" {
  statement {
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:us-east-1:${data.aws_caller_identity.current.account_id}:log-group:/aws/appsync/apis/*"]
  }
}

data "aws_caller_identity" "current" {}

resource "aws_iam_role" "appsync_logs" {
  name               = "lb-demo-realtime-appsync-logs"
  assume_role_policy = data.aws_iam_policy_document.appsync_assume.json
}

resource "aws_iam_role_policy" "appsync_logs" {
  name   = "logs"
  role   = aws_iam_role.appsync_logs.id
  policy = data.aws_iam_policy_document.appsync_logs.json
}
