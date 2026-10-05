# AppSync Events API: browsers connect and subscribe through the Lambda authorizer; only IAM publishes.
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
  }
}

# The channel rule (customers only their own session, staff any) lives in the shared code handler.
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
