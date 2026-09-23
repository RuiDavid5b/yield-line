variable "aws_region" {
  type = string
}

variable "environment" {
  type = string
}

variable "callback_urls" {
  type = list(string)
}

variable "logout_urls" {
  type = list(string)
}
