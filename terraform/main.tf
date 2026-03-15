provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "firestore.googleapis.com",
    "monitoring.googleapis.com",
    "iam.googleapis.com",
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

module "iam" {
  source     = "./modules/iam"
  project_id = var.project_id
  app_name   = var.app_name
  depends_on = [google_project_service.apis]
}

module "artifact_registry" {
  source        = "./modules/artifact_registry"
  project_id    = var.project_id
  region        = var.region
  repository_id = "${var.app_name}-api"
  depends_on    = [google_project_service.apis]
}

module "secret_manager" {
  source     = "./modules/secret_manager"
  project_id = var.project_id
  depends_on = [google_project_service.apis]
}

module "firestore" {
  source      = "./modules/firestore"
  project_id  = var.project_id
  location_id = "nam5"
  depends_on  = [google_project_service.apis]
}

module "cloud_run" {
  source                = "./modules/cloud_run"
  project_id            = var.project_id
  region                = var.region
  app_name              = var.app_name
  image_url             = "${module.artifact_registry.repository_url}/${var.app_name}-api:${var.image_tag}"
  service_account_email = module.iam.service_account_email
  secret_ids            = module.secret_manager.secret_ids
  depends_on = [
    module.iam,
    module.artifact_registry,
    module.secret_manager,
    module.firestore,
  ]
}

module "monitoring" {
  source       = "./modules/monitoring"
  project_id   = var.project_id
  service_name = module.cloud_run.service_name
  alert_email  = var.alert_email
  depends_on   = [module.cloud_run]
}
