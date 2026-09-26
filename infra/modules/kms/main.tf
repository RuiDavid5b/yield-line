resource "aws_kms_key" "byok" {
  description             = "Encrypts user-provided LLM API keys (BYOK)"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "byok" {
  name          = "alias/yieldline-${var.environment}-byok"
  target_key_id = aws_kms_key.byok.key_id
}

# The app runs locally for now, once it's fully migrated to AWS an ECS task 
# role permission is needed to actually use the key.
#resource "aws_iam_role_policy" "backend_kms_access" {
#  name = "yieldline-${var.environment}-byok-kms-access"
#  role = var.backend_role_name
#
#  policy = jsonencode({
#    Version = "2012-10-17"
#    Statement = [{
#      Effect   = "Allow"
#      Action   = ["kms:Encrypt", "kms:Decrypt"]
#      Resource = aws_kms_key.byok.arn
#    }]
#  })
#}
