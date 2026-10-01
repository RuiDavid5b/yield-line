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
  app_secret_arn    = module.secrets.app_secret_arn
}

module "ecr" {
  source      = "../modules/ecr"
  environment = var.environment
}

module "ssm" {
  source               = "../modules/ssm"
  environment          = var.environment
  cookie_domain        = "${module.ec2.public_ip}.sslip.io"
  frontend_origin      = "https://app.${module.ec2.public_ip}.sslip.io"
  cognito_client_id    = module.cognito.client_id
  cognito_user_pool_id = module.cognito.user_pool_id
  byok_kms_key_alias   = module.kms.key_alias
  edgar_user_agent     = var.edgar_user_agent
}

module "secrets" {
  source      = "../modules/secrets"
  environment = var.environment
}

module "github_oidc" {
  source              = "../modules/github_oidc"
  environment         = var.environment
  ecr_repository_arns = module.ecr.repository_arns
}
