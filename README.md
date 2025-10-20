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

### Step 1: Set up Secrets

Store your Slack webhook URL in Secret Manager:

```bash
./setup-secrets.sh "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

### Step 2: Set up Firestore

Ensure Firestore is configured and grant necessary permissions:

```bash
./setup-firestore.sh
```

If Firestore database doesn't exist, you'll need to create it first:

```bash
gcloud firestore databases create \
  --project=moove-data-pipelines \
  --location=us-central1 \
  --type=firestore-native
```

### Step 3: Deploy the Cloud Run Service

Build and deploy the service:

```bash
./deploy.sh
```

This will:
- Build the Docker container using Cloud Build
- Deploy to Cloud Run in `us-central1`
- Configure environment variables and secrets

### Step 4: Set up Pub/Sub Subscription

Create the push subscription to the existing topic:

```bash
./setup-pubsub.sh
```

This will:
- Create a service account for Pub/Sub to invoke Cloud Run
- Grant necessary permissions
- Create the push subscription

## Configuration

### Environment Variables

- `GCP_PROJECT`: GCP project ID (default: `moove-data-pipelines`)
- `SLACK_WEBHOOK_URL`: Slack webhook URL (loaded from Secret Manager)

### Monitored Paths

The service monitors these prefixes in the bucket:
- `Prebind/`
- `Postbind/`
- `test/`

Files outside these paths are ignored.

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
./deploy.sh
```

The Pub/Sub subscription will automatically use the new deployment.

### Update Slack Webhook

```bash
./setup-secrets.sh "NEW_WEBHOOK_URL"
```

Then restart the service:

```bash
gcloud run services update hdvi-folder-notifier \
  --project=moove-data-pipelines \
  --region=us-central1
```

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

