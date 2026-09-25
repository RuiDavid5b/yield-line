module "cognito" {
  source = "../modules/cognito"

  environment = var.environment
  callback_urls = var.callback_urls
  logout_urls = var.logout_urls
}
