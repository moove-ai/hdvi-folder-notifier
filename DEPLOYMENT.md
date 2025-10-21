# Deployment Guide

This document explains how to deploy the HDVI Folder Notifier service.

## Prerequisites

1. **GCP Authentication**: Ensure you're authenticated with `gcloud`
2. **Terraform**: Install Terraform for infrastructure management
3. **GitHub Repository**: Code must be in `moove-ai/hdvi-folder-notifier` repository

## Deployment Methods

### Method 1: Automatic Deployment (Recommended)

#### GitHub Push Trigger
- **When**: Every push to `main` branch
- **What**: Builds + deploys automatically
- **No action required** - just push to `main`

#### GitHub PR Trigger  
- **When**: Pull requests targeting `main`
- **What**: Builds + deploys for testing
- **No action required** - just create PR

### Method 2: Manual Deployment

#### Deploy Infrastructure
```bash
cd terraform
terraform init
terraform apply
```

#### Deploy Service
```bash
# Build and deploy via Cloud Build
gcloud builds submit \
  --project=moove-build \
  --config=cloudbuild.yaml \
  .
```

## First-Time Setup

### 1. Deploy Infrastructure
```bash
cd terraform

# Initialize Terraform
terraform init

# Deploy infrastructure
terraform apply
```

**This creates:**
- Firestore database
- Pub/Sub subscription
- Service accounts and IAM
- Secret Manager secret
- Cloud Build triggers

### 2. Configure Slack Webhook
```bash
gcloud secrets create hdvi-folder-notifier-slack-webhook \
  --project=moove-data-pipelines \
  --data-file=- <<< "YOUR_WEBHOOK_URL"
```

### 3. Deploy Service
```bash
# Trigger Cloud Build manually
gcloud builds submit \
  --project=moove-build \
  --config=cloudbuild.yaml \
  .
```

## Verification

### Check Infrastructure
```bash
# Firestore
gcloud firestore databases describe --project=moove-data-pipelines

# Pub/Sub
gcloud pubsub subscriptions describe hdvi-folder-notifier-sub --project=moove-data-pipelines

# Cloud Run
gcloud run services describe hdvi-folder-notifier --region=us-central1 --project=moove-data-pipelines
```

### Test Service
```bash
# Send test notification
./test-notification.sh Prebind/2024/10/20

# View logs
./view-logs.sh

# Check notified folders
./view-notified-folders.sh
```

## Monitoring

### View Build Status
```bash
# Recent builds
gcloud builds list --project=moove-build --filter="trigger.name~hdvi-folder-notifier" --limit=5

# Cloud Deploy status
gcloud deploy rollouts list --delivery-pipeline=hdvi-folder-notifier --region=us-central1 --project=moove-build
```

### View Service Logs
```bash
# Cloud Run logs
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=hdvi-folder-notifier" --project=moove-data-pipelines --limit=50
```

## Rollback

### Rollback Cloud Deploy
```bash
gcloud deploy rollouts promote \
  --delivery-pipeline=hdvi-folder-notifier \
  --region=us-central1 \
  --project=moove-build \
  --to-target=production-us-central1 \
  --release=RELEASE_NAME
```

### Manual Rollback
```bash
gcloud run services update hdvi-folder-notifier \
  --image=us-docker.pkg.dev/moove-build/docker-us/hdvi-folder-notifier:PREVIOUS_SHA \
  --region=us-central1 \
  --project=moove-data-pipelines
```

## Troubleshooting

### Build Failures
1. Check build logs: `gcloud builds log BUILD_ID --project=moove-build`
2. Verify service account permissions
3. Check Cloud Deploy pipeline status

### Service Issues
1. Check Cloud Run logs: `./view-logs.sh`
2. Verify Firestore permissions
3. Check Slack webhook configuration

### Permission Issues
Ensure `deployer@moove-build.iam.gserviceaccount.com` has:
- `Cloud Build Editor` role
- `Cloud Deploy Admin` role
- `Artifact Registry Writer` role
- `Cloud Run Admin` role (for target project)

## Configuration

### Environment Variables
Set in `service/production.yaml`:
- `GCP_PROJECT`: moove-data-pipelines
- `SLACK_WEBHOOK_URL`: From Secret Manager
- `BUCKET_NAME`: moove-incoming-data-u7x4ty
- `MONITORED_PREFIXES`: Prebind/,Postbind/,test/

### Scaling
Configured in `service/production.yaml`:
- Min instances: 0
- Max instances: 10
- CPU: 1
- Memory: 512Mi
- Concurrency: 80

## Security

- Uses service account authentication
- Secrets stored in Secret Manager
- GitHub webhook uses GCP integration
- All builds run in isolated environment
