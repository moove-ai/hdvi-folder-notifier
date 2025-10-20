# HDVI Folder Notifier - Implementation Summary

## What Was Created

A complete Cloud Run service that monitors GCS bucket notifications and sends Slack alerts for new folders.

### Files Created

```
hdvi-folder-notifier/
├── main.py                      # Main Flask application
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Container definition
├── .dockerignore               # Docker build exclusions
├── .gcloudignore               # Cloud Build exclusions
├── .gitignore                  # Git exclusions
│
├── README.md                    # Full documentation
├── QUICKSTART.md               # Quick reference guide
├── SUMMARY.md                  # This file
│
├── setup-all.sh                # One-command setup (recommended)
├── deploy.sh                   # Deploy Cloud Run service
├── setup-secrets.sh            # Configure Slack webhook
├── setup-firestore.sh          # Configure Firestore
├── setup-pubsub.sh            # Create Pub/Sub subscription
│
├── test-notification.sh        # Send test messages
├── view-logs.sh               # View service logs
└── view-notified-folders.sh   # View Firestore data
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ GCS Bucket: moove-incoming-data-u7x4ty                      │
│   - Prebind/                                                 │
│   - Postbind/                                                │
│   - test/                                                    │
└────────────────┬────────────────────────────────────────────┘
                 │ New file event
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ Pub/Sub Topic: hdvi-process-incoming                        │
└────────────────┬────────────────────────────────────────────┘
                 │ Push subscription
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ Cloud Run: hdvi-folder-notifier                             │
│   - Filters monitored paths                                  │
│   - Checks Firestore for duplicates                          │
│   - Sends Slack notification for new folders                 │
└────────────────┬────────────────────────────────────────────┘
                 │
      ┌──────────┴──────────┐
      ▼                     ▼
┌──────────┐         ┌─────────────┐
│  Slack   │         │  Firestore  │
│  Channel │         │  (tracking) │
└──────────┘         └─────────────┘
```

## Key Features

### 1. Intelligent Filtering
- Only monitors specific folders: `Prebind/`, `Postbind/`, `test/`
- Ignores files in other directories
- Extracts folder path from file path automatically

### 2. Duplicate Prevention
- Uses Firestore transactions to atomically check and mark folders
- Prevents race conditions even with concurrent file arrivals
- Each folder only triggers one notification (guaranteed)
- Stores first notification timestamp

### 3. Robust Error Handling
- Gracefully handles malformed messages
- Retries failed Pub/Sub deliveries
- Logs all operations for debugging

### 4. Scalable Architecture
- Serverless with automatic scaling
- Internal-only ingress for security
- Minimal permissions (least privilege)

## Deployment Steps

### Quick Deployment (Recommended)

```bash
cd /Users/m1/moove-repos/hdvi-folder-notifier
./setup-all.sh "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

### Manual Deployment

```bash
# 1. Configure secrets
./setup-secrets.sh "YOUR_WEBHOOK_URL"

# 2. Setup Firestore
./setup-firestore.sh

# 3. Deploy service
./deploy.sh

# 4. Create subscription
./setup-pubsub.sh
```

## Testing

```bash
# Send test notification for Prebind folder
./test-notification.sh Prebind/2024/10/20

# View logs
./view-logs.sh 20

# Check notified folders
./view-notified-folders.sh
```

## Configuration Details

### Project
- **Project ID**: `moove-data-pipelines`
- **Region**: `us-central1`
- **Service Name**: `hdvi-folder-notifier`

### Resources
- **Topic**: `hdvi-process-incoming` (existing)
- **Subscription**: `hdvi-folder-notifier-sub` (new)
- **Firestore Collection**: `notified_folders`
- **Secret**: `hdvi-folder-notifier-slack-webhook`

### Service Specs
- **Memory**: 512 Mi
- **CPU**: 1
- **Timeout**: 60s
- **Max Instances**: 10
- **Min Instances**: 0 (scales to zero)

## Slack Notification Format

```
📁 New HDVI Data Folder

Folder: moove-incoming-data-u7x4ty/Prebind/2024/10/20
First File Time: 2024-10-20T15:30:00Z
```

## Firestore Schema

**Collection**: `notified_folders`

**Document ID**: Full folder path (e.g., `Prebind/2024/10/20`)

**Fields**:
```javascript
{
  folder: "Prebind/2024/10/20",
  first_notification_time: "2024-10-20T15:30:00Z",
  notified_at: Timestamp // Server timestamp
}
```

## Operations

### View Logs
```bash
./view-logs.sh [limit]
```

### View Notified Folders
```bash
./view-notified-folders.sh
```

### Clear History (Re-enable Notifications)
```bash
gcloud firestore documents delete --all-collections \
  --project=moove-data-pipelines
```

### Update Service
```bash
# Make code changes, then:
./deploy.sh
```

### Update Slack Webhook
```bash
./setup-secrets.sh "NEW_WEBHOOK_URL"
gcloud run services update hdvi-folder-notifier \
  --project=moove-data-pipelines \
  --region=us-central1
```

## Monitoring

### Cloud Console Links
- **Service**: https://console.cloud.google.com/run/detail/us-central1/hdvi-folder-notifier?project=moove-data-pipelines
- **Logs**: https://console.cloud.google.com/logs?project=moove-data-pipelines
- **Firestore**: https://console.cloud.google.com/firestore?project=moove-data-pipelines
- **Pub/Sub**: https://console.cloud.google.com/cloudpubsub?project=moove-data-pipelines

### Key Metrics to Monitor
- Request count and success rate
- Pub/Sub delivery failures
- Firestore write errors
- Slack webhook failures

## Security

- ✅ Service account with minimal permissions
- ✅ Secrets stored in Secret Manager
- ✅ Internal ingress only (no public access)
- ✅ Non-root container user
- ✅ No sensitive data in logs

## Cost Estimate

Expected monthly costs (low traffic):
- Cloud Run: ~$1-2
- Firestore: ~$0.50
- Pub/Sub: ~$0.50
- Cloud Build: ~$1 (deployments)
- **Total**: ~$3-5/month

## Troubleshooting

| Issue | Check | Solution |
|-------|-------|----------|
| No notifications | Logs | `./view-logs.sh` |
| Duplicate notifications | Firestore | `./view-notified-folders.sh` |
| Service errors | Cloud Run Console | Check deployment status |
| Pub/Sub not delivering | Subscription health | Verify push endpoint |

## Next Steps

1. **Deploy**: Run `./setup-all.sh` with your Slack webhook
2. **Test**: Send a test notification with `./test-notification.sh`
3. **Monitor**: Watch logs with `./view-logs.sh`
4. **Verify**: Check Firestore with `./view-notified-folders.sh`

## Support

Questions or issues? Check:
1. Full documentation in [README.md](README.md)
2. Quick reference in [QUICKSTART.md](QUICKSTART.md)
3. Cloud Run logs
4. Firestore data

---

**Created**: October 20, 2024
**Version**: 1.0.0
**Maintainer**: Data Engineering Team

