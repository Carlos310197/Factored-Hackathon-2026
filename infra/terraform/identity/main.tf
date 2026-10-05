# Identity: mock IdP Lambda (container image) behind a throttled HTTP API.
terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
  backend "s3" {
    bucket       = "fh26-tfstate-762197749808-use1"
    key          = "identity/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}

provider "aws" {
  region = "us-east-1"
}

data "terraform_remote_state" "data" {
  backend = "s3"
  config = {
    bucket = "fh26-tfstate-762197749808-use1"
    key    = "data/terraform.tfstate"
    region = "us-east-1"
  }
}

# The data root seeds a placeholder; the image push updates it.
data "aws_ssm_parameter" "image" {
  name = data.terraform_remote_state.data.outputs.identity_image_parameter
}

# Secret container comes from bootstrap; only its ARN is needed.
data "aws_secretsmanager_secret" "signing_key" {
  name = "lb-demo/idp-signing-key"
}
