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
}

run "only_allowed_ips_reach_the_app_port" {
  command = apply

  assert {
    condition     = toset(aws_vpc_security_group_ingress_rule.app[*].cidr_ipv4) == toset(["181.67.2.219/32"])
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
