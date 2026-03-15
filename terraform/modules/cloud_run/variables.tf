variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "app_name" {
  type = string
}

variable "image_url" {
  type = string
}

variable "service_account_email" {
  type = string
}

variable "secret_ids" {
  type    = map(string)
  default = {}
}
