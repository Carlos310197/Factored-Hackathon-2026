resource "aws_s3_bucket" "serving" {
  bucket = local.serving_bucket
}

resource "aws_s3_bucket_policy" "serving" {
  bucket = aws_s3_bucket.serving.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyNonTLS"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.serving.arn, "${aws_s3_bucket.serving.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}

resource "aws_s3_bucket_public_access_block" "serving" {
  bucket                  = aws_s3_bucket.serving.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Trust is read from the integration, so the circular dependency resolves in one apply:
# the integration names this role up front (fixed name), the role then trusts the integration's identity.
resource "aws_iam_role" "snowflake_serving" {
  name = local.snowflake_role_name
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { AWS = snowflake_storage_integration_aws.serving.describe_output[0].iam_user_arn }
      Condition = { StringEquals = { "sts:ExternalId" = snowflake_storage_integration_aws.serving.describe_output[0].external_id } }
    }]
  })
}

resource "aws_iam_role_policy" "snowflake_serving" {
  role = aws_iam_role.snowflake_serving.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.serving.arn}/serving/*"
      },
      {
        Effect    = "Allow"
        Action    = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource  = aws_s3_bucket.serving.arn
        Condition = { StringLike = { "s3:prefix" = ["serving/*"] } }
      },
    ]
  })
}

data "aws_ssm_parameter" "organizer_key_id" {
  name = "/fh26/organizer/aws_key_id"
}

data "aws_ssm_parameter" "organizer_secret" {
  name = "/fh26/organizer/aws_secret"
}

# --- pipeline-runner: CI identity for PIPELINE_SVC. Separate from gha-deploy so each Snowflake user maps to one AWS identity.
# No AWS permissions: every S3 write goes through Snowflake (SERVING_STAGE -> snowflake-serving role).
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_role" "pipeline_runner" {
  name = "pipeline-runner"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRoleWithWebIdentity"
      Principal = { Federated = data.aws_iam_openid_connect_provider.github.arn }
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = ["${local.github_sub_prefix}:ref:refs/heads/main"]
        }
      }
    }]
  })
}
