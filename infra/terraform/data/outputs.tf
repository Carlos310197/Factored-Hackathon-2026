output "table_names" {
  value = { for k, t in aws_dynamodb_table.this : k => t.name }
}

output "table_arns" {
  value = { for k, t in aws_dynamodb_table.this : k => t.arn }
}

output "stream_arns" {
  value = { for k, t in aws_dynamodb_table.this : k => t.stream_arn if t.stream_enabled }
}

output "serving_bucket" {
  value = data.aws_s3_bucket.serving.bucket
}

output "serving_bucket_arn" {
  value = data.aws_s3_bucket.serving.arn
}

output "agent_repository_url" {
  value = aws_ecr_repository.agent.repository_url
}

output "identity_repository_url" {
  value = aws_ecr_repository.identity.repository_url
}

output "agent_image_parameter" {
  value = aws_ssm_parameter.agent_image.name
}

output "identity_image_parameter" {
  value = aws_ssm_parameter.identity_image.name
}
