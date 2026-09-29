resource "aws_kms_key" "byok" {
  description             = "Encrypts user-provided LLM API keys (BYOK)"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "byok" {
  name          = "alias/yieldline-${var.environment}-byok"
  target_key_id = aws_kms_key.byok.key_id
}

resource "aws_iam_policy" "byok_kms_access" {
  name = "yieldline-${var.environment}-byok-kms-access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["kms:Encrypt", "kms:Decrypt"]
      Resource = aws_kms_key.byok.arn
    }]
  })
}

resource "aws_iam_role_policy_attachment" "byok_kms_access" {
  role       = var.backend_role_name
  policy_arn = aws_iam_policy.byok_kms_access.arn
}
