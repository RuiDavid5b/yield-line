output "cognito_user_pool_id" {
  value = module.cognito.user_pool_id
}

output "cognito_client_id" {
  value = module.cognito.client_id
}

output "cognito_user_pool_arn" {
  value = module.cognito.user_pool_arn
}

output "byok_kms_key_arn" {
  value = module.kms.key_arn
}

output "byok_kms_key_alias" {
  value = module.kms.key_alias
}
