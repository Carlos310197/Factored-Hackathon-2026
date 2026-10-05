data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:bedrock-agentcore:us-east-1:${local.account}:*"]
    }
  }
}

locals {
  table_arns = values(data.terraform_remote_state.data.outputs.table_arns)
  log_groups = "arn:aws:logs:us-east-1:${local.account}:log-group:/aws/bedrock-agentcore/runtimes"
}

data "aws_iam_policy_document" "agent" {
  # The LLM client (bankagent.llm.client) sends a short-term Bedrock API key, minted from this role's
  # credentials, to the bedrock-mantle chat-completions endpoint.
  statement {
    actions   = ["bedrock-mantle:CallWithBearerToken"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "bedrock-mantle:BearerTokenType"
      values   = ["SHORT_TERM"]
    }
  }
  statement {
    actions   = ["bedrock-mantle:CreateInference"]
    resources = ["arn:aws:bedrock-mantle:us-east-1:${local.account}:project/*"]
    condition {
      test     = "StringEquals"
      variable = "bedrock-mantle:Model"
      values   = values(local.models)
    }
  }
  # Cross-account Bedrock: the client assumes this role and mints the Mantle token from its credentials.
  statement {
    actions   = ["sts:AssumeRole"]
    resources = [local.bedrock_role_arn]
  }
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${data.terraform_remote_state.data.outputs.serving_bucket_arn}/serving/*"]
  }
  statement {
    actions   = ["s3:ListBucket"]
    resources = [data.terraform_remote_state.data.outputs.serving_bucket_arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["serving/", "serving/*"]
    }
  }
  # Item operations on the six tables and their indexes; no Scan, and deletes only on checkpoints.
  statement {
    actions = [
      "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query",
      "dynamodb:BatchGetItem", "dynamodb:BatchWriteItem", "dynamodb:ConditionCheckItem", "dynamodb:DescribeTable",
    ]
    resources = concat(local.table_arns, [for a in local.table_arns : "${a}/index/*"])
  }
  statement {
    actions   = ["dynamodb:DeleteItem"]
    resources = [data.terraform_remote_state.data.outputs.table_arns["checkpoints"]]
  }
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [data.aws_secretsmanager_secret.jev.arn]
  }
  statement {
    actions   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
    resources = [data.aws_ecr_repository.agent.arn]
  }
  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    actions   = ["logs:CreateLogGroup", "logs:DescribeLogStreams"]
    resources = ["${local.log_groups}/${local.runtime_name}-*"]
  }
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${local.log_groups}/${local.runtime_name}-*:log-stream:*"]
  }
  statement {
    actions   = ["logs:DescribeLogGroups"]
    resources = ["arn:aws:logs:us-east-1:${local.account}:log-group:*"]
  }
  statement {
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"]
    resources = ["*"]
  }
  statement {
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["LatamBank"]
    }
  }
  # AgentCore obtains the workload access token for inbound JWT calls with this role.
  statement {
    actions = ["bedrock-agentcore:GetWorkloadAccessToken", "bedrock-agentcore:GetWorkloadAccessTokenForJWT"]
    resources = [
      "arn:aws:bedrock-agentcore:us-east-1:${local.account}:workload-identity-directory/default",
      "arn:aws:bedrock-agentcore:us-east-1:${local.account}:workload-identity-directory/default/workload-identity/${local.runtime_name}-*",
    ]
  }
}

resource "aws_iam_role" "agent" {
  name               = "lb-demo-agent-exec"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

resource "aws_iam_role_policy" "agent" {
  name   = "agent"
  role   = aws_iam_role.agent.id
  policy = data.aws_iam_policy_document.agent.json
}
