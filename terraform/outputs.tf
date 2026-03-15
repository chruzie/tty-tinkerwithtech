output "api_url" {
  description = "Cloud Run service URL"
  value       = module.cloud_run.service_url
}

output "repository_url" {
  description = "Artifact Registry repository URL"
  value       = module.artifact_registry.repository_url
}

output "service_account_email" {
  description = "API service account email"
  value       = module.iam.service_account_email
}
