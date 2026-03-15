resource "google_cloud_run_v2_service" "api" {
  project  = var.project_id
  name     = var.app_name
  location = var.region

  template {
    service_account = var.service_account_email

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    containers {
      image = var.image_url

      resources {
        limits = { cpu = "1", memory = "256Mi" }
      }

      env {
        name  = "ENVIRONMENT"
        value = "production"
      }
      env {
        name  = "GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "FIRESTORE_PROJECT"
        value = var.project_id
      }

      dynamic "env" {
        for_each = var.secret_ids
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
