terraform {
  backend "s3" {
    bucket       = "fh26-tfstate-762197749808-use1"
    key          = "bootstrap/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}
