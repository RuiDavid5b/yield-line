variable "environment" {
  type = string
}

variable "repository_names" {
  description = "One repository per Dockerfile - the pipeline image and the API image are built separately"
  type        = list(string)
  default     = ["app", "api"]
}

variable "max_image_count" {
  description = "How many images to retain per repository before the oldest expire"
  type        = number
  default     = 3
}
