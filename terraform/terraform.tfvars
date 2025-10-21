# HDVI Folder Notifier - Terraform Variables
# Customize these values as needed

project_id  = "moove-data-pipelines"
region      = "us-central1"
environment = "production"

service_name       = "hdvi-folder-notifier"
topic_name         = "hdvi-process-incoming"
subscription_name  = "hdvi-folder-notifier-sub"
firestore_location = "us-central1"

# Default App Engine service account (Cloud Run default)
cloud_run_service_account = "moove-data-pipelines@appspot.gserviceaccount.com"

# Slack webhook URL (optional - can be set via terraform.tfvars.secret or managed manually)
# slack_webhook_url = ""  # Leave commented to manage secret manually

# Service account for Pub/Sub invoker
pubsub_invoker_sa_name = "hdvi-folder-notifier-invoker"

# Note: Cloud Run configuration (image, memory, CPU, scaling) is in service/production.yaml
# Cloud Run is deployed via Cloud Deploy, not Terraform

# Pub/Sub configuration
ack_deadline_seconds       = 60
message_retention_duration = "604800s" # 7 days
retry_minimum_backoff      = "10s"
retry_maximum_backoff      = "600s"

# Monitoring configuration
# Note: Also update these in service/production.yaml
bucket_name        = "moove-incoming-data-u7x4ty"
monitored_prefixes = "Prebind/,Postbind/,test/"

# Cloud Build triggers
enable_github_triggers = false
github_owner = "moove-ai"
github_repo = "hdvi-folder-notifier"

