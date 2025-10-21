# HDVI Folder Notifier

A Cloud Run service that monitors the `moove-incoming-data-u7x4ty` bucket for new files and sends Slack notifications when new folders are detected in specific directories.

## Overview

This service:
1. Subscribes to the `hdvi-process-incoming` Pub/Sub topic in `moove-data-pipelines`
2. Processes messages about new files in the bucket
3. Filters for files in `Prebind/`, `Postbind/`, and `test/` folders
4. Sends a Slack notification for each unique folder (only on first file)
5. Uses Firestore to track which folders have been notified

## Architecture

```
GCS Bucket (moove-incoming-data-u7x4ty)
    ↓ (new file event)
Pub/Sub Topic (hdvi-process-incoming)
    ↓ (push subscription)
Cloud Run Service (hdvi-folder-notifier)
    ↓ (notification)
Slack Channel
```

## Prerequisites

- `gcloud` CLI installed and configured
- Access to the `moove-data-pipelines` GCP project
- Slack webhook URL for notifications
- Firestore database created in the project

## Deployment

Uses Cloud Deploy for service deployment (like moove-webservice) and Terraform for infrastructure.

### Architecture

- **Service Deployment**: Cloud Deploy + Cloud Build
- **Infrastructure**: Terraform (Firestore, Pub/Sub, IAM)
- **Configuration**: `service/production.yaml`

### Quick Deployment

#### First Time Setup

1. Deploy infrastructure:
```bash
cd terraform
terraform init
terraform apply
```

2. Add Slack webhook:
```bash
# Add your Slack webhook URL to Secret Manager
gcloud secrets create hdvi-folder-notifier-slack-webhook \
  --project=moove-data-pipelines \
  --data-file=- <<< "YOUR_WEBHOOK_URL"
```

3. Deploy service:
```bash
# Automatic: Push to main branch (if triggers enabled)
git push origin main

# Manual: Trigger Cloud Build
gcloud builds submit --project=moove-build --config=cloudbuild.yaml .
```

#### Subsequent Deployments

With Cloud Build triggers enabled:
- **Push to main**: Automatic build + deploy
- **Pull Request**: Automatic build + deploy for testing

Manual deployment:
```bash
gcloud builds submit --project=moove-build --config=cloudbuild.yaml .
```

### Manual Deployment

#### Step 1: Deploy Infrastructure

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

This creates:
- Firestore database
- Secret Manager secrets
- Pub/Sub subscription
- IAM bindings

#### Step 2: Add Secrets

```bash
# Add your Slack webhook URL to Secret Manager
gcloud secrets create hdvi-folder-notifier-slack-webhook \
  --project=moove-data-pipelines \
  --data-file=- <<< "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

#### Step 3: Build and Deploy Service

```bash
gcloud builds submit \
  --project=moove-build \
  --config=cloudbuild.yaml
```

This:
1. Builds container image
2. Pushes to Artifact Registry
3. Triggers Cloud Deploy
4. Deploys to Cloud Run

### Service Configuration

Service configuration is in `service/production.yaml`:
- Memory, CPU limits
- Environment variables
- Health checks
- Scaling parameters

To change service config:
1. Edit `service/production.yaml`
2. Run `gcloud builds submit --project=moove-build --config=cloudbuild.yaml .`

### Benefits

- **Separation of Concerns**: Service vs infrastructure
- **Cloud Deploy**: Standard deployment pipeline with rollbacks
- **Version Control**: Service config alongside code
- **Consistent**: Follows moove-webservice pattern

See [terraform/README.md](terraform/README.md) for Terraform details.

## Configuration

### Environment Variables

- `GCP_PROJECT`: GCP project ID (default: `moove-data-pipelines`)
- `SLACK_WEBHOOK_URL`: Slack webhook URL (loaded from Secret Manager)
- `BUCKET_NAME`: GCS bucket to monitor (default: `moove-incoming-data-u7x4ty`)
- `MONITORED_PREFIXES`: Comma-separated folder prefixes to monitor (default: `Prebind/,Postbind/,test/`)

### Monitored Paths

By default, the service monitors these prefixes:
- `Prebind/`
- `Postbind/`
- `test/`

Files outside these paths are ignored. You can customize this in `terraform/terraform.tfvars`:

```hcl
bucket_name        = "your-bucket-name"
monitored_prefixes = "Folder1/,Folder2/,Folder3/"
```

### Folder Tracking

Firestore collection `notified_folders` stores:
- Document ID: Full folder path (e.g., `Prebind/2024/10/20`)
- Fields:
  - `folder`: The folder path
  - `first_notification_time`: Timestamp from the first file event
  - `notified_at`: Server timestamp when notification was sent

**Concurrency Safety**: Uses Firestore transactions to atomically check and mark folders, preventing duplicate notifications even when multiple files arrive simultaneously.

## Testing

### Manual Testing

Send a test Pub/Sub message:

```bash
gcloud pubsub topics publish hdvi-process-incoming \
  --project=moove-data-pipelines \
  --message='{"name":"Prebind/2024/10/20/test.csv","bucket":"moove-incoming-data-u7x4ty","timeCreated":"2024-10-20T12:00:00Z"}'
```

### Check Logs

View Cloud Run logs:

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=hdvi-folder-notifier" \
  --project=moove-data-pipelines \
  --limit=50 \
  --format=json
```

Or via Cloud Console:
https://console.cloud.google.com/run/detail/us-central1/hdvi-folder-notifier/logs?project=moove-data-pipelines

### Check Firestore

View tracked folders:

```bash
gcloud firestore documents list notified_folders \
  --project=moove-data-pipelines
```

## Slack Notification Format

Notifications include:
- **Header**: "📁 New HDVI Data Folder"
- **Folder**: Full path (e.g., `moove-incoming-data-u7x4ty/Prebind/2024/10/20`)
- **First File Time**: Timestamp from the first file event

## Monitoring

### Key Metrics

- Request count
- Request latency
- Error rate
- Container CPU/Memory utilization

View metrics in Cloud Console:
https://console.cloud.google.com/run/detail/us-central1/hdvi-folder-notifier/metrics?project=moove-data-pipelines

### Alerts

Consider setting up alerts for:
- High error rates
- Failed Pub/Sub message deliveries
- Firestore write failures

## Troubleshooting

### No notifications received

1. Check Cloud Run logs for errors
2. Verify Pub/Sub subscription is delivering messages
3. Check that Slack webhook URL is correct in Secret Manager
4. Verify file paths match monitored prefixes

### Duplicate notifications

1. Check Firestore for existing folder entries
2. Review logs for Firestore write failures
3. Ensure Firestore permissions are correct

### Service not receiving messages

1. Verify Pub/Sub subscription exists and is active
2. Check that the push endpoint URL is correct
3. Verify service account has Cloud Run Invoker role
4. Check that the service is deployed and running

## Maintenance

### Update the Service

Make code changes and redeploy:

```bash
gcloud builds submit --project=moove-build --config=cloudbuild.yaml .
```

Or manually:
```bash
# Build new image
gcloud builds submit --config=cloudbuild.yaml

# Update Terraform
cd terraform
terraform apply
```

The Pub/Sub subscription will automatically use the new deployment.

### Update Slack Webhook

```bash
# Update your Slack webhook URL in Secret Manager
gcloud secrets versions add hdvi-folder-notifier-slack-webhook \
  --project=moove-data-pipelines \
  --data-file=- <<< "NEW_WEBHOOK_URL"
```

Cloud Run automatically picks up the new secret version (configured to use "latest").

### Clear Notification History

To reset and get notifications for all folders again:

```bash
# Delete all documents in the collection
gcloud firestore documents delete --all-collections \
  --project=moove-data-pipelines
```

**Warning**: This will re-notify for all folders when new files arrive.

## Cost Considerations

- **Cloud Run**: Pay per request and compute time
- **Firestore**: Pay per read/write operation and storage
- **Pub/Sub**: Pay per message delivery
- **Cloud Build**: Pay per build minute

Typical costs are minimal for this service (< $5/month).

## Security

- Service uses minimal IAM permissions
- Ingress limited to internal traffic only
- Secrets stored in Secret Manager
- Service account follows principle of least privilege

## Future Enhancements

Potential improvements:
- Add filtering by file type/pattern
- Configurable monitored paths via environment variables
- Support for multiple Slack channels based on folder prefix
- Dead letter queue for failed notifications
- Scheduled summary reports
- Web UI for viewing notification history

## Support

For issues or questions:
1. Check Cloud Run logs
2. Review Firestore data
3. Verify Pub/Sub subscription health
4. Contact the data engineering team

