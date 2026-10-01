resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com"
  ]

  tags = {
    Project     = "yieldline"
    Environment = var.environment
  }
}

resource "aws_iam_role" "github_actions" {
  name = "yieldline-${var.environment}-github-actions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"

      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }

        StringLike = {
          "token.actions.githubusercontent.com:sub" = [
            "repo:RuiDavid5b@147104500/yield-line@1310312310:pull_request",
            "repo:RuiDavid5b@147104500/yield-line@1310312310:ref:refs/heads/*"
          ]
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "ecr_push" {
  name = "yieldline-${var.environment}-ecr-push"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability", "ecr:PutImage",
          "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload",
        ]
        Resource = var.ecr_repository_arns
      }
    ]
  })
}

resource "aws_iam_role_policy" "ssm_send_command" {
  name = "yieldline-${var.environment}-deploy-trigger"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:SendCommand", "ssm:GetCommandInvocation"]
      Resource = "*"
    }]
  })
}
