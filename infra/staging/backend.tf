terraform {
  backend "s3" {
    bucket       = "yieldline-tf-state-56d0872d-2f38-4ae7-a494-4b6fb49a18b6"
    key          = "yieldline/staging/terraform.tfstate"
    region       = "eu-west-2"
    use_lockfile = true
  }
}
