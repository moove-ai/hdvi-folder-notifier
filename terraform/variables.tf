variable "project_id" {
  description = "The GCP project ID"
  type        = string
  default     = "moove-data-pipelines"
}

variable "region" {
  description = "The GCP region for Cloud Run service"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "service_name" {
  description = "The Cloud Run service name"
  type        = string
  default     = "hdvi-folder-notifier"
}

variable "topic_name" {
  description = "The existing Pub/Sub topic name to subscribe to"
  type        = string
  default     = "hdvi-process-incoming"
}

variable "subscription_name" {
  description = "The Pub/Sub subscription name to create"
  type        = string
  default     = "hdvi-folder-notifier-sub"
}

variable "cloud_run_service_account" {
  description = "The service account used by Cloud Run (default App Engine service account)"
  type        = string
  default     = "moove-data-pipelines@appspot.gserviceaccount.com"
}

variable "firestore_location" {
  description = "The Firestore database location"
  type        = string
  default     = "us-central1"
}

variable "slack_webhook_url" {
  description = "Slack webhook URL (leave empty to manage manually)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "slack_webhook_secret_name" {
  description = "Secret Manager secret name for Slack webhook"
  type        = string
  default     = "hdvi-folder-notifier-slack-webhook"
}

variable "pubsub_invoker_sa_name" {
  description = "Service account name for Pub/Sub to invoke Cloud Run"
  type        = string
  default     = "hdvi-folder-notifier-invoker"
}

variable "ack_deadline_seconds" {
  description = "Pub/Sub subscription acknowledgement deadline in seconds"
  type        = number
  default     = 60
}

variable "message_retention_duration" {
  description = "How long to retain unacknowledged messages (e.g., '604800s' for 7 days)"
  type        = string
  default     = "604800s"
}

variable "retry_minimum_backoff" {
  description = "Minimum backoff for retry policy"
  type        = string
  default     = "10s"
}

variable "retry_maximum_backoff" {
  description = "Maximum backoff for retry policy"
  type        = string
  default     = "600s"
}

# Cloud Build trigger variables
variable "enable_github_triggers" {
  description = "Enable automatic GitHub push/PR triggers"
  type        = bool
  default     = true
}

variable "github_owner" {
  description = "GitHub repository owner"
  type        = string
  default     = "moove-ai"
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "hdvi-folder-notifier"
}

variable "bucket_name" {
  description = "GCS bucket name to monitor for new files"
  type        = string
  default     = "moove-incoming-data-u7x4ty"
}

variable "monitored_prefixes" {
  description = "Comma-separated list of folder prefixes to monitor (e.g., 'Prebind/,Postbind/,test/')"
  type        = string
  default     = "Prebind/,Postbind/,test/"
}

# Note: Cloud Run configuration (memory, CPU, scaling) is in service/production.yaml
# These variables are kept for reference but not used by Terraform

