output "issuer" {
  value = aws_apigatewayv2_api.this.api_endpoint
}

output "jwks_url" {
  value = "${aws_apigatewayv2_api.this.api_endpoint}/jwks.json"
}

output "api_id" {
  value = aws_apigatewayv2_api.this.id
}

output "function_name" {
  value = aws_lambda_function.identity.function_name
}
