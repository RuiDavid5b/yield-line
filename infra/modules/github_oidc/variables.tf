variable "environment" {
  type = string
}

variable "ecr_repository_arns" {
  type = list(string)
}

variable "frontend_bucket_name" {
  type = string
}
