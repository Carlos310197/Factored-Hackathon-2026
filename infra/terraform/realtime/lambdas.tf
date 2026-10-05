locals {
  stream_arns = data.terraform_remote_state.data.outputs.stream_arns
  dist        = "${path.module}/../../realtime/dist"
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

data "archive_file" "authorizer" {
  type        = "zip"
  source_dir  = "${local.dist}/authorizer"
  output_path = "${path.module}/.build/authorizer.zip"
}

data "archive_file" "publisher" {
  type        = "zip"
  source_dir  = "${local.dist}/publisher"
  output_path = "${path.module}/.build/publisher.zip"
}

# ---- DLQ for records the publisher cannot deliver

resource "aws_sqs_queue" "dlq" {
  name                      = "lb-demo-realtime-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

data "aws_iam_policy_document" "dlq" {
  statement {
    sid       = "DenyNonTls"
    effect    = "Deny"
    actions   = ["sqs:*"]
    resources = [aws_sqs_queue.dlq.arn]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_sqs_queue_policy" "dlq" {
  queue_url = aws_sqs_queue.dlq.url
  policy    = data.aws_iam_policy_document.dlq.json
}

# ---- Authorizer

resource "aws_cloudwatch_log_group" "authorizer" {
  name              = "/aws/lambda/lb-demo-realtime-authorizer"
  retention_in_days = 30
}

data "aws_iam_policy_document" "authorizer" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.authorizer.arn}:*"]
  }
  statement {
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
    resources = ["*"]
  }
}

resource "aws_iam_role" "authorizer" {
  name               = "lb-demo-realtime-authorizer"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

resource "aws_iam_role_policy" "authorizer" {
  name   = "authorizer"
  role   = aws_iam_role.authorizer.id
  policy = data.aws_iam_policy_document.authorizer.json
}

resource "aws_lambda_function" "authorizer" {
  function_name    = "lb-demo-realtime-authorizer"
  role             = aws_iam_role.authorizer.arn
  runtime          = "nodejs22.x"
  handler          = "index.handler"
  architectures    = ["arm64"]
  filename         = data.archive_file.authorizer.output_path
  source_code_hash = data.archive_file.authorizer.output_base64sha256
  memory_size      = 256
  timeout          = 5

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      IDP_ISSUER   = data.terraform_remote_state.identity.outputs.issuer
      IDP_JWKS_URL = data.terraform_remote_state.identity.outputs.jwks_url
    }
  }

  depends_on = [aws_cloudwatch_log_group.authorizer, aws_iam_role_policy.authorizer]
}

# ---- Publisher: DynamoDB Streams to Events channels

resource "aws_cloudwatch_log_group" "publisher" {
  name              = "/aws/lambda/lb-demo-realtime-publisher"
  retention_in_days = 30
}

data "aws_iam_policy_document" "publisher" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.publisher.arn}:*"]
  }
  statement {
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
    resources = ["*"]
  }
  statement {
    actions   = ["appsync:EventPublish"]
    resources = ["${aws_appsync_api.this.api_arn}/channelNamespace/*"]
  }
  statement {
    actions   = ["dynamodb:GetRecords", "dynamodb:GetShardIterator", "dynamodb:DescribeStream"]
    resources = values(local.stream_arns)
  }
  statement {
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.dlq.arn]
  }
}

resource "aws_iam_role" "publisher" {
  name               = "lb-demo-realtime-publisher"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

resource "aws_iam_role_policy" "publisher" {
  name   = "publisher"
  role   = aws_iam_role.publisher.id
  policy = data.aws_iam_policy_document.publisher.json
}

resource "aws_lambda_function" "publisher" {
  function_name    = "lb-demo-realtime-publisher"
  role             = aws_iam_role.publisher.arn
  runtime          = "nodejs22.x"
  handler          = "index.handler"
  architectures    = ["arm64"]
  filename         = data.archive_file.publisher.output_path
  source_code_hash = data.archive_file.publisher.output_base64sha256
  memory_size      = 256
  timeout          = 30

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      EVENTS_HTTP_DOMAIN = aws_appsync_api.this.dns["HTTP"]
    }
  }

  depends_on = [aws_cloudwatch_log_group.publisher, aws_iam_role_policy.publisher]
}

resource "aws_lambda_event_source_mapping" "stream" {
  for_each = local.stream_arns

  event_source_arn                   = each.value
  function_name                      = aws_lambda_function.publisher.arn
  starting_position                  = "LATEST"
  batch_size                         = 25
  bisect_batch_on_function_error     = true
  maximum_retry_attempts             = 5
  function_response_types            = ["ReportBatchItemFailures"]
  maximum_batching_window_in_seconds = 0

  destination_config {
    on_failure {
      destination_arn = aws_sqs_queue.dlq.arn
    }
  }
}
