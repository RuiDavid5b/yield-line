output "key_arn" {
  value = aws_kms_key.byok.arn
}

output "key_alias" {
  value = aws_kms_alias.byok.name
}
