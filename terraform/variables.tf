variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run and Artifact Registry"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Deployment environment (production | staging)"
  type        = string
  default     = "production"
}

variable "app_name" {
  description = "Application name used as prefix for resource names"
  type        = string
  default     = "tty-theme"
}

variable "alert_email" {
  description = "Email address for Cloud Monitoring alert notifications"
  type        = string
  default     = ""
}

variable "image_tag" {
  description = "Docker image tag to deploy to Cloud Run"
  type        = string
  default     = "latest"
}
