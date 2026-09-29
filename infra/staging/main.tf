module "cognito" {
  source      = "../modules/cognito"
  environment = var.environment
}

module "kms" {
  source            = "../modules/kms"
  environment       = var.environment
  backend_role_name = module.ec2.role_name
}

module "ec2" {
  source            = "../modules/ec2"
  environment       = var.environment
  ssh_ingress_cidr  = var.ssh_ingress_cidr
  availability_zone = var.availability_zone
}
