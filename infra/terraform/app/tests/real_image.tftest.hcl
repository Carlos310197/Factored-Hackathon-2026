# Separate file = separate state: the SSM parameter ignores value changes, so a run in app.tftest.hcl would keep the placeholder.
mock_provider "aws" {
  mock_data "aws_ec2_managed_prefix_list" {
    defaults = { id = "pl-3b927c52" }
  }
  mock_resource "aws_cloudfront_distribution" {
    defaults = { domain_name = "d1234abcd.cloudfront.net", arn = "arn:aws:cloudfront::762197749808:distribution/E123" }
  }
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

run "real_image_drops_the_command_override" {
  command = apply

  # a fresh apply whose parameter already holds the pushed image (ECR url is mocked, so match on it)
  variables {
    image = "mock-ecr-url:abc1234"
  }

  assert {
    condition     = local.image == "mock-ecr-url:abc1234"
    error_message = "the task uses the SSM parameter value"
  }

  assert {
    condition     = jsondecode(aws_ecs_task_definition.web.container_definitions)[0].command == null
    error_message = "real image runs its own CMD (no command override)"
  }
}
