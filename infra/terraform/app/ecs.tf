resource "aws_ecr_repository" "web" {
  name                 = "latam-bank-web"
  image_tag_mutability = "IMMUTABLE" # tags are git SHAs
  force_delete         = true
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "web" {
  repository = aws_ecr_repository.web.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "keep the last 10 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 10 }
      action       = { type = "expire" }
    }]
  })
}

resource "aws_cloudwatch_log_group" "web" {
  name              = "/ecs/latam-bank-web"
  retention_in_days = 30
}

resource "aws_ecs_cluster" "main" {
  name = "latam-bank"
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE_SPOT", "FARGATE"]
  default_capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 1
  }
}

resource "aws_security_group" "web" {
  name        = "latam-bank-web"
  description = "Web UI: team IPs only, until the demo ALB exists"
  vpc_id      = data.aws_vpc.default.id
}

resource "aws_vpc_security_group_ingress_rule" "app" {
  count             = length(var.allowed_cidrs)
  security_group_id = aws_security_group.web.id
  cidr_ipv4         = var.allowed_cidrs[count.index]
  ip_protocol       = "tcp"
  from_port         = 3000
  to_port           = 3000
}

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.web.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

locals {
  ecs_tasks_trust = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ecs-tasks.amazonaws.com" } }]
  })
}

# ECS agent: pull images, write logs.
resource "aws_iam_role" "execution" {
  name               = "latam-bank-web-execution"
  assume_role_policy = local.ecs_tasks_trust
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# App code (the BFF): DynamoDB only (no InvokeAgentRuntime: it calls the agent over its HTTPS URL, no Scan, no Secrets Manager).
resource "aws_iam_role" "task" {
  name               = "latam-bank-web-task"
  assume_role_policy = local.ecs_tasks_trust
}

locals {
  table_arns = data.terraform_remote_state.data.outputs.table_arns
  # TransactWriteItems has no IAM action of its own: it is authorized by the Put/UpdateItem on each item's table.
  rw_tables = [for t in ["sessions", "conversation_messages", "handoffs"] : local.table_arns[t]]
  ro_tables = [local.table_arns["decision_records"]]
  # The BFF's environment. No secret belongs here (use the task definition's `secrets` from Secrets Manager).
  web_env = {
    PORT                           = "3000"
    HOSTNAME                       = "0.0.0.0"
    IDP_URL                        = data.terraform_remote_state.identity.outputs.issuer
    IDP_ISSUER                     = data.terraform_remote_state.identity.outputs.issuer
    IDP_AUDIENCE                   = "bankagent"
    STAFF_AUDIENCE                 = "bankagent-staff"
    AGENTCORE_INVOKE_URL           = data.terraform_remote_state.agent.outputs.invoke_url
    AWS_REGION                     = "us-east-1"
    TABLE_PREFIX                   = "lb-demo"
    DEMO_MODE                      = "1"
    CHAT_ASYNC                     = "0"
    COOKIE_SECURE                  = "0"                                                      # plain HTTP on the task public IP until the demo ALB
    NEXT_PUBLIC_EVENTS_HTTP_DOMAIN = data.terraform_remote_state.realtime.outputs.http_domain # also baked at build time (Dockerfile build arg)
    NEXT_PUBLIC_EVENTS_REGION      = "us-east-1"
  }
  # The real image runs its own CMD; the placeholder needs the command override.
  image = nonsensitive(aws_ssm_parameter.web_image.value)
}

data "aws_iam_policy_document" "task" {
  statement {
    sid       = "ReadWriteTables"
    actions   = ["dynamodb:GetItem", "dynamodb:Query", "dynamodb:PutItem", "dynamodb:UpdateItem"]
    resources = concat(local.rw_tables, [for a in local.rw_tables : "${a}/index/*"])
  }
  statement {
    sid       = "ReadDecisionRecords"
    actions   = ["dynamodb:GetItem", "dynamodb:Query"]
    resources = local.ro_tables
  }
}

resource "aws_iam_role_policy" "task" {
  name   = "dynamodb"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task.json
}

resource "aws_ecs_task_definition" "web" {
  family                   = "latam-bank-web"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([{
    name         = "web"
    image        = local.image
    command      = strcontains(local.image, aws_ecr_repository.web.repository_url) ? null : var.command
    essential    = true
    portMappings = [{ containerPort = 3000, protocol = "tcp" }]
    environment  = [for k, v in local.web_env : { name = k, value = v }]
    healthCheck = {
      command     = ["CMD-SHELL", "wget -qO- http://127.0.0.1:3000/ >/dev/null || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 30
    }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.web.name
        awslogs-region        = "us-east-1"
        awslogs-stream-prefix = "web"
      }
    }
  }])
}

resource "aws_ecs_service" "web" {
  name                               = "latam-bank-web"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.web.arn
  desired_count                      = 1
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  wait_for_steady_state              = true
  capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 1
  }
  network_configuration {
    subnets          = data.aws_subnets.public.ids
    security_groups  = [aws_security_group.web.id]
    assign_public_ip = true
  }
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  depends_on = [aws_ecs_cluster_capacity_providers.main]
}
