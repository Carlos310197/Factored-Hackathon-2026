resource "aws_ecr_repository" "agent" {
  name                 = "lb-demo-agent"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "identity" {
  name                 = "lb-demo-identity"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

locals {
  keep_last_10 = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 10 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 10 }
      action       = { type = "expire" }
    }]
  })
}

resource "aws_ecr_lifecycle_policy" "agent" {
  repository = aws_ecr_repository.agent.name
  policy     = local.keep_last_10
}

resource "aws_ecr_lifecycle_policy" "identity" {
  repository = aws_ecr_repository.identity.name
  policy     = local.keep_last_10
}

# Placeholder values; the deploy workflow overwrites them with the pushed image URI.
resource "aws_ssm_parameter" "agent_image" {
  name  = "/fh26/agent/image"
  type  = "String"
  value = "placeholder"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "identity_image" {
  name  = "/fh26/identity/image"
  type  = "String"
  value = "placeholder"

  lifecycle {
    ignore_changes = [value]
  }
}
