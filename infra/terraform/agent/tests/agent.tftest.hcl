variables {
  bedrock_role_arn    = "arn:aws:iam::111111111111:role/ai-account-bedrock-role"
  bedrock_external_id = "test-external-id"
}

mock_provider "aws" {
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
  mock_data "aws_lb" {
    defaults = { arn_suffix = "app/latam-bank-web/0123456789abcdef" }
  }
  mock_data "aws_caller_identity" {
    defaults = { account_id = "762197749808" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::762197749808:role/lb-demo-agent-exec" }
  }
  mock_resource "aws_sns_topic" {
    defaults = { arn = "arn:aws:sns:us-east-1:762197749808:lb-demo-agent-alarms" }
  }
  mock_resource "aws_bedrockagentcore_agent_runtime" {
    defaults = {
      agent_runtime_id      = "lb_demo_agent-AbC123xYz0"
      agent_runtime_arn     = "arn:aws:bedrock-agentcore:us-east-1:762197749808:runtime/lb_demo_agent-AbC123xYz0"
      agent_runtime_version = "3"
    }
  }
}

override_data {
  target = data.terraform_remote_state.data
  values = {
    outputs = {
      agent_image_parameter = "/fh26/agent/image"
      serving_bucket        = "latam-bank-serving-762197749808-use1"
      serving_bucket_arn    = "arn:aws:s3:::latam-bank-serving-762197749808-use1"
      table_arns = {
        checkpoints           = "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-checkpoints"
        disputes              = "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-disputes"
        handoffs              = "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-handoffs"
        decision_records      = "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-decision_records"
        sessions              = "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-sessions"
        conversation_messages = "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-conversation_messages"
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

override_data {
  target = data.aws_ssm_parameter.image
  values = { value = "762197749808.dkr.ecr.us-east-1.amazonaws.com/lb-demo-agent:abc1234" }
}

override_data {
  target = data.aws_secretsmanager_secret.jev
  values = { arn = "arn:aws:secretsmanager:us-east-1:762197749808:secret:lb-demo/jev-AbCdEf" }
}

override_data {
  target = data.aws_ecr_repository.agent
  values = { arn = "arn:aws:ecr:us-east-1:762197749808:repository/lb-demo-agent" }
}

run "runtime_shape" {
  command = apply

  assert {
    condition     = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_name == "lb_demo_agent"
    error_message = "runtime name lb_demo_agent"
  }
  assert {
    condition     = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_artifact[0].container_configuration[0].container_uri == "762197749808.dkr.ecr.us-east-1.amazonaws.com/lb-demo-agent:abc1234"
    error_message = "container from /fh26/agent/image"
  }
  assert {
    condition     = aws_bedrockagentcore_agent_runtime.agent.network_configuration[0].network_mode == "PUBLIC" && aws_bedrockagentcore_agent_runtime.agent.protocol_configuration[0].server_protocol == "HTTP"
    error_message = "PUBLIC network, HTTP protocol"
  }
  assert {
    condition     = aws_bedrockagentcore_agent_runtime.agent.authorizer_configuration[0].custom_jwt_authorizer[0].discovery_url == "https://idp123.execute-api.us-east-1.amazonaws.com/.well-known/openid-configuration"
    error_message = "JWT discovery URL is the issuer's OpenID configuration"
  }
  assert {
    condition     = aws_bedrockagentcore_agent_runtime.agent.authorizer_configuration[0].custom_jwt_authorizer[0].allowed_audience == toset(["bankagent"])
    error_message = "allowed audience bankagent"
  }
  assert {
    condition     = contains(aws_bedrockagentcore_agent_runtime.agent.request_header_configuration[0].request_header_allowlist, "Authorization")
    error_message = "Authorization header reaches the agent"
  }
  assert {
    condition     = aws_bedrockagentcore_agent_runtime.agent.role_arn == aws_iam_role.agent.arn
    error_message = "runtime uses the execution role"
  }
}

run "runtime_environment_has_no_secret_values" {
  command = apply

  assert {
    condition = aws_bedrockagentcore_agent_runtime.agent.environment_variables == tomap({
      TABLE_PREFIX        = "lb-demo"
      SERVING_URI         = "s3://latam-bank-serving-762197749808-use1/serving/"
      IDP_ISSUER          = "https://idp123.execute-api.us-east-1.amazonaws.com"
      IDP_AUDIENCE        = "bankagent"
      IDP_JWKS_URL        = "https://idp123.execute-api.us-east-1.amazonaws.com/jwks.json"
      LLM_EXTRACT_MODEL   = "mistral.ministral-3-14b-instruct"
      LLM_COMPOSE_MODEL   = "openai.gpt-oss-120b"
      GIT_SHA             = "abc1234"
      JEV_SECRET_ID       = "lb-demo/jev"
      BEDROCK_ROLE_ARN    = "arn:aws:iam::111111111111:role/ai-account-bedrock-role"
      BEDROCK_EXTERNAL_ID = "test-external-id"
      RESOLVER_ARTIFACT   = "/app/src/bankagent/resolver/artifacts/v1"
      THRESHOLDS_FILE     = "/app/src/bankagent/decisions/thresholds.v2.yaml"
    })
    error_message = "agent environment (names only, no secret values)"
  }
  assert {
    condition     = alltrue([for k in keys(aws_bedrockagentcore_agent_runtime.agent.environment_variables) : !can(regex("API_KEY|PASSWORD|TOKEN", k))])
    error_message = "no secret-valued variables"
  }
}

run "live_endpoint_tracks_the_new_version" {
  command = apply

  assert {
    condition     = aws_bedrockagentcore_agent_runtime_endpoint.live.name == "live" && aws_bedrockagentcore_agent_runtime_endpoint.live.agent_runtime_id == "lb_demo_agent-AbC123xYz0"
    error_message = "endpoint live on this runtime"
  }
  assert {
    condition     = aws_bedrockagentcore_agent_runtime_endpoint.live.agent_runtime_version == "3"
    error_message = "endpoint pins the version this apply produced"
  }
  assert {
    condition     = aws_cloudwatch_log_group.runtime.name == "/aws/bedrock-agentcore/runtimes/lb_demo_agent-AbC123xYz0-live" && aws_cloudwatch_log_group.runtime.retention_in_days == 30
    error_message = "live endpoint log group kept 30 days"
  }
}

run "execution_role_trusts_agentcore_in_this_account" {
  command = apply

  assert {
    condition     = aws_iam_role.agent.name == "lb-demo-agent-exec"
    error_message = "role name"
  }
  assert {
    condition     = one(data.aws_iam_policy_document.assume.statement[0].principals).identifiers == toset(["bedrock-agentcore.amazonaws.com"])
    error_message = "trusts bedrock-agentcore"
  }
  assert {
    condition     = anytrue([for c in data.aws_iam_policy_document.assume.statement[0].condition : c.test == "StringEquals" && c.variable == "aws:SourceAccount" && c.values == tolist(["762197749808"])])
    error_message = "aws:SourceAccount is this account"
  }
}

run "least_privilege_data_access" {
  command = apply

  assert {
    condition     = !anytrue([for a in flatten([for s in data.aws_iam_policy_document.agent.statement : tolist(s.actions)]) : contains(["dynamodb:Scan", "dynamodb:*", "s3:*", "bedrock-mantle:*", "bedrock:*"], a)])
    error_message = "no Scan, no service wildcards"
  }
  assert {
    condition = alltrue([for s in data.aws_iam_policy_document.agent.statement :
      toset(s.resources) == toset(["arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-checkpoints"])
    if contains(tolist(s.actions), "dynamodb:DeleteItem")])
    error_message = "DeleteItem only on checkpoints"
  }
  assert {
    condition     = length([for s in data.aws_iam_policy_document.agent.statement : s if contains(tolist(s.actions), "dynamodb:DeleteItem")]) == 1
    error_message = "exactly one DeleteItem statement"
  }
  assert {
    condition     = contains(flatten([for s in data.aws_iam_policy_document.agent.statement : tolist(s.resources) if contains(tolist(s.actions), "dynamodb:Query")]), "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-disputes/index/*")
    error_message = "item operations cover table indexes"
  }
  assert {
    condition     = contains(flatten([for s in data.aws_iam_policy_document.agent.statement : tolist(s.resources) if contains(tolist(s.actions), "s3:GetObject")]), "arn:aws:s3:::latam-bank-serving-762197749808-use1/serving/*")
    error_message = "S3 reads only under serving/"
  }
  assert {
    condition     = flatten([for s in data.aws_iam_policy_document.agent.statement : tolist(s.resources) if contains(tolist(s.actions), "secretsmanager:GetSecretValue")]) == ["arn:aws:secretsmanager:us-east-1:762197749808:secret:lb-demo/jev-AbCdEf"]
    error_message = "only the Jev secret"
  }
  assert {
    condition     = anytrue([for s in data.aws_iam_policy_document.agent.statement : contains(tolist(s.actions), "bedrock-mantle:CreateInference") && anytrue([for c in s.condition : c.variable == "bedrock-mantle:Model" && toset(c.values) == toset(["mistral.ministral-3-14b-instruct", "openai.gpt-oss-120b"])])])
    error_message = "Mantle inference limited to the two configured models"
  }
  assert {
    condition     = anytrue([for s in data.aws_iam_policy_document.agent.statement : contains(tolist(s.actions), "cloudwatch:PutMetricData") && anytrue([for c in s.condition : c.variable == "cloudwatch:namespace" && c.values == tolist(["LatamBank"])])])
    error_message = "PutMetricData only in namespace LatamBank"
  }
}

run "invoke_url_uses_the_live_qualifier" {
  command = apply

  assert {
    condition     = output.invoke_url == "https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aus-east-1%3A762197749808%3Aruntime%2Flb_demo_agent-AbC123xYz0/invocations?qualifier=live"
    error_message = "invoke URL with the url-encoded ARN and qualifier=live"
  }
  assert {
    condition     = output.runtime_id == "lb_demo_agent-AbC123xYz0" && output.runtime_arn == "arn:aws:bedrock-agentcore:us-east-1:762197749808:runtime/lb_demo_agent-AbC123xYz0"
    error_message = "runtime id and arn outputs"
  }
}

run "alarms" {
  command = apply

  assert {
    condition     = length(aws_cloudwatch_log_metric_filter.agent) == 6
    error_message = "one metric filter per watched log line (turn failed, template fallback, audit write, slow turn, stale pointer, turn cap)"
  }
  assert {
    condition     = aws_cloudwatch_log_metric_filter.agent["TemplateFallback"].pattern == "\"reply fell back to template\""
    error_message = "the template-fallback filter must match the agent's log line exactly"
  }
  assert {
    condition     = aws_cloudwatch_metric_alarm.agent["TurnFailed"].threshold == 3 && aws_cloudwatch_metric_alarm.agent["TurnFailed"].treat_missing_data == "notBreaching"
    error_message = "turn failures alarm at 3 in 5 minutes; no traffic is not an alarm"
  }
  assert {
    condition     = length(aws_sns_topic.alarms) == 0 && length(aws_budgets_budget.account) == 0
    error_message = "no notification topic or budget unless alarm_email is set"
  }
}

run "alarms_notify_by_email" {
  command = apply
  variables {
    alarm_email = "ops@example.com"
  }
  assert {
    condition     = length(aws_sns_topic.alarms) == 1 && length(aws_cloudwatch_metric_alarm.agent["TurnFailed"].alarm_actions) == 1
    error_message = "with alarm_email set, every alarm notifies the topic"
  }
  assert {
    condition     = length(aws_budgets_budget.account) == 1 && aws_budgets_budget.account[0].limit_amount == "100"
    error_message = "with alarm_email set, a monthly account budget emails at 80 % actual / 100 % forecast"
  }
}

run "dashboard_reads_turn_latency_and_every_alarm" {
  command = apply

  assert {
    condition     = aws_cloudwatch_log_metric_filter.turn_duration.pattern == "[event=\"turn_end\", duration_ms]" && aws_cloudwatch_log_metric_filter.turn_duration.metric_transformation[0].value == "$duration_ms"
    error_message = "TurnDurationMs comes from the agent's `turn_end <ms>` line"
  }
  assert {
    condition     = length(jsondecode(aws_cloudwatch_dashboard.ops.dashboard_body).widgets) == 7 && strcontains(aws_cloudwatch_dashboard.ops.dashboard_body, "TurnDurationMs") && strcontains(aws_cloudwatch_dashboard.ops.dashboard_body, "app/latam-bank-web/")
    error_message = "dashboard shows latency, failures, abuse, alarms, the web load balancer and requests by outcome"
  }
  assert {
    condition     = aws_cloudwatch_log_metric_filter.requests.pattern == "[event=\"request\", outcome, session, message]" && aws_cloudwatch_log_metric_filter.requests.metric_transformation[0].dimensions["Outcome"] == "$outcome"
    error_message = "every agent request is counted by outcome"
  }
}
