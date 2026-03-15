locals {
  secrets = ["GEMINI_API_KEY", "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"]
}

resource "google_secret_manager_secret" "secrets" {
  for_each  = toset(local.secrets)
  project   = var.project_id
  secret_id = each.value

  replication {
    auto {}
  }
}
