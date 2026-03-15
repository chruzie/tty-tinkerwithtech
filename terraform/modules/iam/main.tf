resource "google_service_account" "api" {
  project      = var.project_id
  account_id   = "${var.app_name}-api"
  display_name = "${var.app_name} API"
}

locals {
  roles = [
    "roles/datastore.user",
    "roles/secretmanager.secretAccessor",
    "roles/monitoring.metricWriter",
  ]
}

resource "google_project_iam_member" "api_roles" {
  for_each = toset(local.roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.api.email}"
}
