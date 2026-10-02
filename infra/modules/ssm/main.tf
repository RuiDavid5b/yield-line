locals {
  plain_params = {
    cookie_domain        = var.cookie_domain
    frontend_origin      = var.frontend_origin
    cognito_client_id    = var.cognito_client_id
    cognito_user_pool_id = var.cognito_user_pool_id
    byok_kms_key_alias   = var.byok_kms_key_alias
    edgar_user_agent     = var.edgar_user_agent
  }
}

resource "aws_ssm_parameter" "plain" {
  for_each = local.plain_params

  name  = "/stock-news/${var.environment}/${each.key}"
  type  = "String"
  value = each.value
}
