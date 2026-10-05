output "http_domain" {
  value = aws_appsync_api.this.dns["HTTP"]
}

output "realtime_domain" {
  value = aws_appsync_api.this.dns["REALTIME"]
}

output "api_arn" {
  value = aws_appsync_api.this.api_arn
}

output "dlq_name" {
  value = aws_sqs_queue.dlq.name
}

output "publisher_name" {
  value = aws_lambda_function.publisher.function_name
}

output "authorizer_name" {
  value = aws_lambda_function.authorizer.function_name
}

output "api_id" {
  value = aws_appsync_api.this.api_id
}
