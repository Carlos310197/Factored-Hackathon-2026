# Data: retained DynamoDB tables, ECR repositories and image parameters. Table shapes come from
# tables.json, exported from agent TABLE_SPECS (agent/scripts/export_table_specs.py).
terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
  backend "s3" {
    bucket       = "fh26-tfstate-762197749808-use1"
    key          = "data/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}

provider "aws" {
  region = "us-east-1"
}

locals {
  tables = jsondecode(file("${path.module}/tables.json"))
}

# Terraform platform owns the bucket; this root only reads it.
data "aws_s3_bucket" "serving" {
  bucket = "latam-bank-serving-762197749808-use1"
}
