mock_provider "aws" {
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
  mock_resource "aws_appsync_api" {
    defaults = {
      api_id  = "abcd1234"
      api_arn = "arn:aws:appsync:us-east-1:762197749808:apis/abcd1234"
      dns     = { HTTP = "abcd1234.appsync-api.us-east-1.amazonaws.com", REALTIME = "abcd1234.appsync-realtime-api.us-east-1.amazonaws.com" }
    }
  }
  mock_data "aws_caller_identity" {
    defaults = { account_id = "762197749808" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::762197749808:role/lb-demo-realtime" }
  }
  mock_resource "aws_cloudwatch_log_group" {
    defaults = { arn = "arn:aws:logs:us-east-1:762197749808:log-group:/aws/lambda/lb-demo-realtime" }
  }
  mock_resource "aws_sqs_queue" {
    defaults = { arn = "arn:aws:sqs:us-east-1:762197749808:lb-demo-realtime-dlq" }
  }
  mock_resource "aws_lambda_function" {
    defaults = { arn = "arn:aws:lambda:us-east-1:762197749808:function:lb-demo-realtime-authorizer" }
  }
}

# dist/ is built by `npm run build`; the archive data sources are mocked so tests don't need it
mock_provider "archive" {
  mock_data "archive_file" {
    defaults = { output_base64sha256 = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=" }
  }
}

override_data {
  target = data.terraform_remote_state.data
  values = {
    outputs = {
      stream_arns = {
        handoffs              = "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-handoffs/stream/2026-10-05T00:00:00.000"
        decision_records      = "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-decision_records/stream/2026-10-05T00:00:00.000"
        conversation_messages = "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-conversation_messages/stream/2026-10-05T00:00:00.000"
      }
    }
  }
}

override_data {
  target = data.terraform_remote_state.identity
  values = {
    outputs = {
      issuer   = "https://idp123.execute-api.us-east-1.amazonaws.com"
      jwks_url = "https://idp123.execute-api.us-east-1.amazonaws.com/jwks.json"
    }
  }
}

run "event_api_with_three_namespaces" {
  command = apply

  assert {
    condition     = aws_appsync_api.this.name == "lb-demo-realtime"
    error_message = "one Event API named lb-demo-realtime"
  }
  assert {
    condition     = toset(keys(aws_appsync_channel_namespace.this)) == toset(["session", "queue", "trace"]) && alltrue([for n in aws_appsync_channel_namespace.this : n.code_handlers == file("${path.module}/../../realtime/handlers/namespace.js")])
    error_message = "session, queue and trace namespaces, each with the shared code handler"
  }
}

run "publish_is_iam_only_and_subscribe_is_lambda" {
  command = apply

  assert {
    condition     = [for m in aws_appsync_api.this.event_config[0].default_publish_auth_mode : m.auth_type] == ["AWS_IAM"]
    error_message = "publish is AWS_IAM only"
  }
  assert {
    condition     = [for m in aws_appsync_api.this.event_config[0].default_subscribe_auth_mode : m.auth_type] == ["AWS_LAMBDA"] && [for m in aws_appsync_api.this.event_config[0].connection_auth_mode : m.auth_type] == ["AWS_LAMBDA"]
    error_message = "connect and subscribe use the Lambda authorizer"
  }
  assert {
    condition     = aws_lambda_permission.appsync.principal == "appsync.amazonaws.com" && aws_lambda_permission.appsync.source_arn == "arn:aws:appsync:us-east-1:762197749808:apis/abcd1234"
    error_message = "AppSync may invoke the authorizer, from this API only"
  }
}

run "three_stream_sources_with_bisect_retries_and_dlq" {
  command = apply

  assert {
    condition     = toset(keys(aws_lambda_event_source_mapping.stream)) == toset(["handoffs", "decision_records", "conversation_messages"])
    error_message = "one mapping per stream"
  }
  assert {
    condition = alltrue([for m in aws_lambda_event_source_mapping.stream :
      m.bisect_batch_on_function_error && m.maximum_retry_attempts == 5 && m.starting_position == "LATEST"
      && m.function_response_types == toset(["ReportBatchItemFailures"])
    && m.destination_config[0].on_failure[0].destination_arn == "arn:aws:sqs:us-east-1:762197749808:lb-demo-realtime-dlq"])
    error_message = "bisect, 5 retries, partial-batch responses, LATEST, failures to the DLQ"
  }
}

run "publisher_can_publish_and_authorizer_knows_the_issuer" {
  command = apply

  assert {
    condition = aws_lambda_function.authorizer.environment[0].variables == tomap({
      IDP_ISSUER   = "https://idp123.execute-api.us-east-1.amazonaws.com"
      IDP_JWKS_URL = "https://idp123.execute-api.us-east-1.amazonaws.com/jwks.json"
    })
    error_message = "authorizer env from the identity root"
  }
  assert {
    condition     = aws_lambda_function.publisher.environment[0].variables == tomap({ EVENTS_HTTP_DOMAIN = "abcd1234.appsync-api.us-east-1.amazonaws.com" })
    error_message = "publisher env carries the Events HTTP domain"
  }
  assert {
    condition     = alltrue([for f in [aws_lambda_function.authorizer, aws_lambda_function.publisher] : f.runtime == "nodejs22.x" && f.architectures == tolist(["arm64"]) && f.handler == "index.handler" && f.tracing_config[0].mode == "Active"])
    error_message = "Node 22 arm64, X-Ray active"
  }
  assert {
    condition     = contains(flatten([for s in data.aws_iam_policy_document.publisher.statement : s.actions]), "appsync:EventPublish") && contains(flatten([for s in data.aws_iam_policy_document.publisher.statement : s.actions]), "sqs:SendMessage")
    error_message = "publisher policy has EventPublish and DLQ send"
  }
  assert {
    condition     = alltrue([for g in [aws_cloudwatch_log_group.authorizer, aws_cloudwatch_log_group.publisher] : g.retention_in_days == 30])
    error_message = "30-day log groups"
  }
  assert {
    condition     = output.http_domain == "abcd1234.appsync-api.us-east-1.amazonaws.com" && output.dlq_name == "lb-demo-realtime-dlq"
    error_message = "outputs"
  }
}

run "dlq_retains_14_days_and_requires_tls" {
  command = apply

  assert {
    condition     = aws_sqs_queue.dlq.message_retention_seconds == 1209600 && aws_sqs_queue.dlq.sqs_managed_sse_enabled
    error_message = "14-day retention, SSE on"
  }
  assert {
    condition     = alltrue([for s in data.aws_iam_policy_document.dlq.statement : s.effect == "Deny" && length([for c in s.condition : c if c.variable == "aws:SecureTransport" && contains(c.values, "false")]) == 1])
    error_message = "queue policy denies non-TLS"
  }
}

run "event_api_logs_handler_output_to_a_30_day_group" {
  command = apply

  assert {
    condition     = aws_appsync_api.this.event_config[0].log_config[0].log_level == "ERROR" && aws_appsync_api.this.event_config[0].log_config[0].cloudwatch_logs_role_arn == aws_iam_role.appsync_logs.arn
    error_message = "default log level ERROR with the logs role"
  }
  assert {
    condition     = aws_cloudwatch_log_group.appsync.name == "/aws/appsync/apis/abcd1234" && aws_cloudwatch_log_group.appsync.retention_in_days == 30
    error_message = "declared AppSync log group, 30 days"
  }
  assert {
    condition     = contains(flatten([for s in data.aws_iam_policy_document.appsync_assume.statement : [for p in s.principals : p.identifiers]]), "appsync.amazonaws.com") && !contains(flatten([for s in data.aws_iam_policy_document.publisher.statement : s.actions]), "dynamodb:ListStreams")
    error_message = "appsync assumes the logs role; ListStreams dropped"
  }
  assert {
    condition     = output.api_id == "abcd1234"
    error_message = "api_id output"
  }
}
