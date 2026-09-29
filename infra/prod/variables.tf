variable "aws_region" {
  type = string
}

variable "availability_zone" {
  description = "AZ within aws_region to deploy into"
  type        = string
}

variable "environment" {
  type = string
}

variable "ssh_ingress_cidr" {
  description = "Your own IP, as a /32 CIDR"
  type        = string
}
