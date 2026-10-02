variable "availability_zone" {
  type = string
}

variable "environment" {
  type = string
}

variable "ssh_ingress_cidr" {
  description = "Your own IP, as a /32 CIDR"
  type        = string
}

variable "instance_type" {
  type    = string
  default = "t4g.small"
}

variable "data_volume_size_gb" {
  type    = number
  default = 8
}

variable "app_secret_arn" {
  type = string
}
