variable "environment" {
  type = string
}

variable "database_url" {
  type      = string
  sensitive = true
}

variable "redis_url" {
  type      = string
  sensitive = true
}

variable "cookie_domain" {
  type = string
}

variable "frontend_origin" {
  type = string
}

variable "cognito_client_id" {
  type = string
}

variable "cognito_user_pool_id" {
  type = string
}

variable "byok_kms_key_alias" {
  type = string
}

variable "edgar_user_agent" {
  type = string
}

variable "google_api_key" {
  type      = string
  sensitive = true
}

variable "currents_api_key" {
  type      = string
  sensitive = true
}
