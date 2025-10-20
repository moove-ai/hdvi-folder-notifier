# HDVI Folder Notifier - Quick Start

## One-Command Setup

```bash
./setup-all.sh "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

That's it! This will:
1. Store Slack webhook in Secret Manager
2. Configure Firestore permissions  
3. Deploy the Cloud Run service
4. Create the Pub/Sub subscription

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

### Create Firestore Database

If Firestore doesn't exist:

```bash
gcloud firestore databases create \
  --project=moove-data-pipelines \
  --location=us-central1 \
  --type=firestore-native
```

### Individual Setup Steps

```bash
# 1. Store Slack webhook
./setup-secrets.sh "YOUR_WEBHOOK_URL"

# 2. Configure Firestore
./setup-firestore.sh

# 3. Deploy service
./deploy.sh

# 4. Create subscription
./setup-pubsub.sh
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

