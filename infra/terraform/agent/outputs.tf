output "runtime_id" {
  value = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_id
}

output "runtime_arn" {
  value = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_arn
}

output "invoke_url" {
  value = "https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/${urlencode(aws_bedrockagentcore_agent_runtime.agent.agent_runtime_arn)}/invocations?qualifier=${aws_bedrockagentcore_agent_runtime_endpoint.live.name}"
}
