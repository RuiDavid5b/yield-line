variable "environment" {
  type = string
}

variable "repository_names" {
  description = "One repository per deployable Docker image"
  type        = list(string)
  default     = ["backend", "api", "frontend", "airflow"]
}

variable "max_image_count" {
  description = "How many images to retain per repository before the oldest expire"
  type        = number
  default     = 3
}
