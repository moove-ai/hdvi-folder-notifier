# HDVI Folder Notifier - Quick Start

## One-Command Deployment

```bash
gcloud builds submit --project=moove-build --config=cloudbuild.yaml .
```

This builds and deploys via Cloud Deploy. First-time setup also requires:

```bash
# 1. Deploy infrastructure (Firestore, Pub/Sub, secrets)
cd terraform && terraform init && terraform apply

# 2. Add Slack webhook
# Add your Slack webhook URL to Secret Manager
gcloud secrets create hdvi-folder-notifier-slack-webhook \
  --project=moove-data-pipelines \
  --data-file=- <<< "YOUR_WEBHOOK_URL"

# 3. Deploy service
gcloud builds submit --project=moove-build --config=cloudbuild.yaml .
```

## Architecture

**Service Deployment**: Cloud Deploy (like moove-webservice)
**Infrastructure**: Terraform (Firestore, Pub/Sub, IAM)

## Test It

```bash
./test-notification.sh Prebind/2024/10/20
```

Check your Slack channel for the notification!

## View Activity

```bash
# View logs
./view-logs.sh

# View notified folders
./view-notified-folders.sh
```

## How It Works

1. New file lands in `moove-incoming-data-u7x4ty/Prebind/`, `/Postbind/`, or `/test/`
2. GCS publishes to `hdvi-process-incoming` topic
3. Service receives message via push subscription
4. If folder hasn't been notified before → Slack notification sent
5. Folder tracked in Firestore to prevent duplicates

## Manual Steps (if needed)

### Deploy Infrastructure Only

```bash
cd terraform && terraform init && terraform apply
```

Or manually:
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### Build and Deploy Service Only

```bash
gcloud builds submit --project=moove-build --config=cloudbuild.yaml
```

This builds the image and triggers Cloud Deploy.

### Manage Slack Webhook

```bash
# Add webhook (via helper script)
# Add your Slack webhook URL to Secret Manager
gcloud secrets create hdvi-folder-notifier-slack-webhook \
  --project=moove-data-pipelines \
  --data-file=- <<< "YOUR_WEBHOOK_URL"

# Or directly
echo -n "YOUR_WEBHOOK_URL" | gcloud secrets versions add hdvi-folder-notifier-slack-webhook \
  --project=moove-data-pipelines \
  --data-file=-
```

## Troubleshooting

**No notifications?**
- Check logs: `./view-logs.sh`
- Verify webhook: Check Secret Manager in GCP Console
- Test manually: `./test-notification.sh Prebind/test`

**Duplicate notifications?**
- Check Firestore: `./view-notified-folders.sh`
- May indicate Firestore write failures

**Service not starting?**
- Check Cloud Run console for deployment errors
- Verify all APIs are enabled (Cloud Run, Firestore, Secret Manager)

## Need Help?

See [README.md](README.md) for full documentation.

