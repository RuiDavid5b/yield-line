module "cognito" {
  source = "../modules/cognito"

  environment   = var.environment
  callback_urls = var.callback_urls
  logout_urls   = var.logout_urls
}

module "kms" {
  source = "../modules/kms"

  environment = var.environment
  #backend_role_name = module.ecs.backend_task_role_name
}
