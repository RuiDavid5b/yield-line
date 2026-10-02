resource "aws_secretsmanager_secret" "app" {
  name        = "yieldline/${var.environment}/app-secrets"
  description = "Runtime secrets for YieldLine ${var.environment}"

  tags = {
    Environment = var.environment
    Project     = "yieldline"
  }
}

output "app_secret_arn" {
  value = aws_secretsmanager_secret.app.arn
}

output "app_secret_name" {
  value = aws_secretsmanager_secret.app.name
}
