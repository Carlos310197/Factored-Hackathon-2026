terraform {
  backend "s3" {
    bucket       = "fh26-tfstate-762197749808"
    key          = "bootstrap/terraform.tfstate"
    region       = "us-east-2"
    use_lockfile = true
  }
}
