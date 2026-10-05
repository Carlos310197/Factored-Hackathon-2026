mock_provider "aws" {
  mock_resource "aws_lb" {
    defaults = { arn = "arn:aws:elasticloadbalancing:us-east-1:762197749808:loadbalancer/app/latam-bank-web/abc", dns_name = "latam-bank-web-123.us-east-1.elb.amazonaws.com" }
  }
  mock_resource "aws_lb_target_group" {
    defaults = { arn = "arn:aws:elasticloadbalancing:us-east-1:762197749808:targetgroup/latam-bank-web/abc" }
  }
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

run "public_alb_and_the_task_only_reachable_through_it" {
  command = apply

  assert {
    condition     = aws_lb.web.internal == false && aws_lb.web.load_balancer_type == "application" && length(aws_lb.web.subnets) >= 2
    error_message = "internet-facing ALB across at least two public subnets"
  }

  assert {
    condition     = aws_vpc_security_group_ingress_rule.alb_http.cidr_ipv4 == "0.0.0.0/0" && aws_vpc_security_group_ingress_rule.alb_http.from_port == 80
    error_message = "the ALB is public on port 80 (no domain, so no certificate)"
  }

  assert {
    condition     = aws_vpc_security_group_ingress_rule.app.referenced_security_group_id == aws_security_group.alb.id && aws_vpc_security_group_ingress_rule.app.from_port == 3000 && aws_vpc_security_group_ingress_rule.app.cidr_ipv4 == null
    error_message = "the task port admits only the ALB's security group, no CIDR (no home IPs)"
  }

  assert {
    condition     = aws_lb_target_group.web.target_type == "ip" && aws_lb_target_group.web.port == 3000 && aws_lb_target_group.web.health_check[0].path == "/login"
    error_message = "IP target group on 3000, health-checked on /login"
  }

  assert {
    condition     = one(aws_ecs_service.web.load_balancer).container_port == 3000 && one(aws_ecs_service.web.load_balancer).container_name == "web"
    error_message = "the service registers its task with the target group"
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
