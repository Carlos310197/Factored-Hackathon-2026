resource "aws_bedrockagentcore_agent_runtime" "agent" {
  agent_runtime_name = local.runtime_name
  description        = "LATAM Bank customer-service agent (demo)"
  role_arn           = aws_iam_role.agent.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = local.image
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  protocol_configuration {
    server_protocol = "HTTP"
  }

  authorizer_configuration {
    custom_jwt_authorizer {
      discovery_url    = "${local.issuer}/.well-known/openid-configuration"
      allowed_audience = [local.audience]
    }
  }

  # The BFF sends the message id in the custom header; listing it documents the dependency (agent README).
  request_header_configuration {
    request_header_allowlist = ["Authorization", "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Message-Id"]
  }

  # Names only: the Jev key is read from Secrets Manager at start (bankagent.settings.load_settings).
  # table_name() joins prefix and name with "-", so "lb-demo" gives lb-demo-<name>.
  environment_variables = {
    TABLE_PREFIX      = "lb-demo"
    SERVING_URI       = "s3://${data.terraform_remote_state.data.outputs.serving_bucket}/serving/"
    IDP_ISSUER        = local.issuer
    IDP_AUDIENCE      = local.audience
    IDP_JWKS_URL      = data.terraform_remote_state.identity.outputs.jwks_url
    LLM_EXTRACT_MODEL = local.models.extract
    LLM_COMPOSE_MODEL = local.models.compose
    GIT_SHA           = element(split(":", local.image), length(split(":", local.image)) - 1)
    JEV_SECRET_ID     = data.aws_secretsmanager_secret.jev.name
  }

  lifecycle {
    precondition {
      condition     = can(regex("^\\d{12}\\.dkr\\.ecr\\.[a-z0-9-]+\\.amazonaws\\.com/lb-demo-agent:[^:@/]+$", local.image))
      error_message = "/fh26/agent/image must hold a pushed lb-demo-agent image URI (repo:tag); push the image first."
    }
  }

  # AgentCore validates the role when it creates the runtime.
  depends_on = [aws_iam_role_policy.agent]
}

# AgentCore logs to /aws/bedrock-agentcore/runtimes/<runtime id>-<endpoint>; created before the endpoint so
# Terraform owns its retention.
resource "aws_cloudwatch_log_group" "runtime" {
  name              = "/aws/bedrock-agentcore/runtimes/${aws_bedrockagentcore_agent_runtime.agent.agent_runtime_id}-${local.endpoint}"
  retention_in_days = 30
}

resource "aws_bedrockagentcore_agent_runtime_endpoint" "live" {
  name                  = local.endpoint
  agent_runtime_id      = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_id
  agent_runtime_version = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_version

  depends_on = [aws_cloudwatch_log_group.runtime]
}
