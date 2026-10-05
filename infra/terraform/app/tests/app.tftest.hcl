mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "762197749808" }
  }
  mock_data "aws_vpc" {
    defaults = { id = "vpc-0746f651cab477517" }
  }
  mock_data "aws_subnets" {
    defaults = { ids = ["subnet-a", "subnet-b"] }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::762197749808:role/mock" }
  }
  mock_resource "aws_ecr_repository" {
    defaults = { repository_url = "mock-ecr-url" }
  }
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
}

override_data {
  target = data.terraform_remote_state.data
  values = {
    outputs = {
      table_arns = {
        sessions              = "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-sessions"
        conversation_messages = "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-conversation_messages"
        handoffs              = "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-handoffs"
        decision_records      = "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-decision_records"
        checkpoints           = "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-checkpoints"
        disputes              = "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-disputes"
      }
    }
  }
}

override_data {
  target = data.terraform_remote_state.identity
  values = { outputs = { issuer = "https://idp123.execute-api.us-east-1.amazonaws.com" } }
}

override_data {
  target = data.terraform_remote_state.agent
  values = { outputs = { invoke_url = "https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/x/invocations" } }
}

override_data {
  target = data.terraform_remote_state.realtime
  values = { outputs = { http_domain = "abc.appsync-api.us-east-1.amazonaws.com" } }
}

run "only_allowed_ips_reach_the_app_port" {
  command = apply

  assert {
    condition     = toset(aws_vpc_security_group_ingress_rule.app[*].cidr_ipv4) == toset(["181.67.2.219/32", "38.25.85.60/32"])
    error_message = "ingress must be exactly the allowed /32s"
  }

  assert {
    condition     = alltrue([for r in aws_vpc_security_group_ingress_rule.app : r.from_port == 3000 && r.to_port == 3000 && r.ip_protocol == "tcp"])
    error_message = "ingress only on tcp/3000"
  }
}

run "spot_only_public_ip_no_load_balancer" {
  command = apply

  assert {
    condition     = length(aws_ecs_service.web.capacity_provider_strategy) == 1 && one(aws_ecs_service.web.capacity_provider_strategy).capacity_provider == "FARGATE_SPOT"
    error_message = "service must run on FARGATE_SPOT only"
  }

  assert {
    condition     = aws_ecs_service.web.network_configuration[0].assign_public_ip && length(aws_ecs_service.web.load_balancer) == 0
    error_message = "public IP, no load balancer (until demo day)"
  }

  assert {
    condition     = aws_ecs_service.web.deployment_circuit_breaker[0].rollback
    error_message = "circuit breaker with rollback"
  }
}

run "valid_fargate_size_and_awsvpc" {
  command = apply

  assert {
    condition     = aws_ecs_task_definition.web.cpu == "512" && aws_ecs_task_definition.web.memory == "1024" && aws_ecs_task_definition.web.network_mode == "awsvpc"
    error_message = "0.5 vCPU / 1 GB, awsvpc"
  }
}

run "task_role_policy_is_dynamodb_only_on_the_bff_tables" {
  command = apply

  assert {
    condition = alltrue([for st in data.aws_iam_policy_document.task.statement :
    alltrue([for a in st.actions : startswith(a, "dynamodb:") && a != "dynamodb:Scan"])])
    error_message = "task role: dynamodb only, no Scan, no InvokeAgentRuntime"
  }

  assert {
    condition = toset(flatten([for st in data.aws_iam_policy_document.task.statement : st.resources])) == toset([
      "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-sessions",
      "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-sessions/index/*",
      "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-conversation_messages",
      "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-conversation_messages/index/*",
      "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-handoffs",
      "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-handoffs/index/*",
      "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-decision_records",
    ])
    error_message = "only sessions, conversation_messages, handoffs (+indexes) and decision_records"
  }

  assert {
    condition     = [for st in data.aws_iam_policy_document.task.statement : st.actions if contains(st.resources, "arn:aws:dynamodb:us-east-1:762197749808:table/lb-demo-decision_records")][0] == toset(["dynamodb:GetItem", "dynamodb:Query"])
    error_message = "decision_records is read-only"
  }
}

run "container_environment_has_every_env_ts_key_and_no_secret" {
  command = apply

  assert {
    condition = alltrue([for k in ["IDP_URL", "IDP_ISSUER", "IDP_AUDIENCE", "STAFF_AUDIENCE", "AGENTCORE_INVOKE_URL", "AWS_REGION", "TABLE_PREFIX", "DEMO_MODE", "CHAT_ASYNC", "COOKIE_SECURE", "NEXT_PUBLIC_EVENTS_HTTP_DOMAIN"] :
    contains(keys(local.web_env), k)])
    error_message = "environment must carry every key web/lib/server/env.ts needs"
  }

  assert {
    condition     = local.web_env.TABLE_PREFIX == "lb-demo" && local.web_env.IDP_URL == "https://idp123.execute-api.us-east-1.amazonaws.com" && local.web_env.AGENTCORE_INVOKE_URL == "https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/x/invocations"
    error_message = "values come from the other roots"
  }

  assert {
    condition     = !contains(keys(local.web_env), "E2E_MOCK") && alltrue([for k in keys(local.web_env) : !can(regex("(?i)secret|password|key|token", k))])
    error_message = "no secret and never E2E_MOCK in environment"
  }
}

run "image_comes_from_the_ssm_parameter" {
  command = apply

  assert {
    condition     = aws_ssm_parameter.web_image.name == "/fh26/web/image" && jsondecode(aws_ecs_task_definition.web.container_definitions)[0].image == local.image
    error_message = "task definition uses the /fh26/web/image value"
  }

  assert {
    condition     = jsondecode(aws_ecs_task_definition.web.container_definitions)[0].command != null
    error_message = "placeholder image keeps the command override"
  }
}
