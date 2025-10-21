output "pubsub_invoker_service_account" {
  description = "Service account email for Pub/Sub to invoke Cloud Run"
  value       = google_service_account.pubsub_invoker.email
}

output "subscription_name" {
  description = "The created Pub/Sub subscription name"
  value       = google_pubsub_subscription.notifier_subscription.name
}

output "subscription_id" {
  description = "The full subscription ID"
  value       = google_pubsub_subscription.notifier_subscription.id
}

# Note: These outputs will be available after Cloud Run service is deployed
# output "cloud_run_service_url" {
#   description = "The Cloud Run service URL"
#   value       = data.google_cloud_run_v2_service.notifier.uri
# }
#
# output "cloud_run_service_name" {
#   description = "The Cloud Run service name"
#   value       = data.google_cloud_run_v2_service.notifier.name
# }

output "slack_webhook_secret_id" {
  description = "The Secret Manager secret ID for Slack webhook"
  value       = google_secret_manager_secret.slack_webhook.secret_id
}

output "topic_name" {
  description = "The Pub/Sub topic name"
  value       = data.google_pubsub_topic.hdvi_incoming.name
}

output "firestore_database_name" {
  description = "The Firestore database name"
  value       = google_firestore_database.database.name
}

output "firestore_location" {
  description = "The Firestore database location"
  value       = google_firestore_database.database.location_id
}

output "bucket_name" {
  description = "The GCS bucket being monitored"
  value       = var.bucket_name
}

output "monitored_prefixes" {
  description = "The folder prefixes being monitored"
  value       = var.monitored_prefixes
}

