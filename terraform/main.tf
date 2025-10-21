/**
 * HDVI Folder Notifier Infrastructure
 * 
 * Sets up supporting infrastructure only. Cloud Run is deployed via Cloud Deploy.
 * 
 * Resources created:
 * - Pub/Sub push subscription to hdvi-process-incoming topic
 * - Service account for Pub/Sub to invoke Cloud Run
 * - IAM bindings for Firestore access
 * - Secret Manager secret for Slack webhook
 * - Firestore database
 * 
 * Note: Cloud Run service itself is deployed via cloudbuild.yaml -> Cloud Deploy
 */

terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Data source for the existing Pub/Sub topic
data "google_pubsub_topic" "hdvi_incoming" {
  name    = var.topic_name
  project = var.project_id
}

# Data source for the Cloud Run service (deployed via Cloud Deploy)
# Cloud Run service (deployed via Cloud Deploy, not Terraform)
# Note: This data source will be available after the first Cloud Run deployment
# data "google_cloud_run_v2_service" "notifier" {
#   name     = var.service_name
#   location = var.region
#   project  = var.project_id
# }

# Secret Manager secret for Slack webhook
resource "google_secret_manager_secret" "slack_webhook" {
  secret_id = var.slack_webhook_secret_name
  project   = var.project_id

  replication {
    auto {}
  }

  labels = {
    terraformed = "true"
    environment = var.environment
    service     = var.service_name
    app         = "hdvi-folder-notifier"
  }

  lifecycle {
    # Prevent accidental deletion of the secret
    prevent_destroy = true
  }
}

# Secret version (create this manually or use lifecycle to ignore changes)
# Note: The actual secret value should be added manually or via separate process
resource "google_secret_manager_secret_version" "slack_webhook_version" {
  count = var.slack_webhook_url != "" ? 1 : 0

  secret      = google_secret_manager_secret.slack_webhook.id
  secret_data = var.slack_webhook_url

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Grant Cloud Run service account access to the secret
resource "google_secret_manager_secret_iam_member" "secret_accessor" {
  secret_id = google_secret_manager_secret.slack_webhook.secret_id
  project   = var.project_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.cloud_run_service_account}"
}

# Note: Cloud Run service is deployed via Cloud Deploy, not Terraform
# See: service/production.yaml, clouddeploy.yaml, and cloudbuild.yaml

# Service account for Pub/Sub to invoke Cloud Run
resource "google_service_account" "pubsub_invoker" {
  project      = var.project_id
  account_id   = var.pubsub_invoker_sa_name
  display_name = "HDVI Folder Notifier - Pub/Sub Invoker"
  description  = "Service account for Pub/Sub to invoke the HDVI folder notifier Cloud Run service"
}

# Grant the service account permission to invoke the Cloud Run service
# Note: This will be added after Cloud Run service is deployed
# resource "google_cloud_run_v2_service_iam_member" "invoker" {
#   project  = var.project_id
#   location = var.region
#   name     = data.google_cloud_run_v2_service.notifier.name
#   role     = "roles/run.invoker"
#   member   = "serviceAccount:${google_service_account.pubsub_invoker.email}"
# }

# Create push subscription to the existing topic
resource "google_pubsub_subscription" "notifier_subscription" {
  name    = var.subscription_name
  project = var.project_id
  topic   = data.google_pubsub_topic.hdvi_incoming.name

  ack_deadline_seconds       = var.ack_deadline_seconds
  message_retention_duration = var.message_retention_duration

  push_config {
    push_endpoint = "https://hdvi-folder-notifier-184386668605.us-central1.run.app/"
    
    oidc_token {
      service_account_email = google_service_account.pubsub_invoker.email
    }
    
    attributes = {
      x-goog-version = "v1"
    }
  }

  retry_policy {
    minimum_backoff = var.retry_minimum_backoff
    maximum_backoff = var.retry_maximum_backoff
  }

  expiration_policy {
    ttl = "" # Never expire
  }

  labels = {
    terraformed = "true"
    environment = var.environment
    service     = var.service_name
    app         = "hdvi-folder-notifier"
  }

  # depends_on = [
  #   google_cloud_run_v2_service_iam_member.invoker
  # ]
}

# Firestore database
# Note: Firestore databases cannot be deleted via Terraform
# If you need to destroy this, set prevent_destroy = false first, or delete via console
resource "google_firestore_database" "database" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"

  # Prevent accidental deletion
  lifecycle {
    prevent_destroy = true
  }
}

# Grant the default Cloud Run service account Firestore access
resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${var.cloud_run_service_account}"

  depends_on = [
    google_firestore_database.database
  ]
}

