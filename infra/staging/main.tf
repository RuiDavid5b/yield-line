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

module "ecr" {
  source      = "../modules/ecr"
  environment = var.environment
}

module "ssm" {
  source               = "../modules/ssm"
  environment          = var.environment
  database_url         = var.database_url
  redis_url            = var.redis_url
  cookie_domain        = "${module.ec2.public_ip}.sslip.io"
  frontend_origin      = "https://app.${module.ec2.public_ip}.sslip.io"
  cognito_client_id    = module.cognito.client_id
  cognito_user_pool_id = module.cognito.user_pool_id
  byok_kms_key_alias   = module.kms.key_alias
  edgar_user_agent     = var.edgar_user_agent
  google_api_key       = var.google_api_key
  currents_api_key     = var.currents_api_key
}
