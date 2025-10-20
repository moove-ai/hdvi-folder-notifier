#!/bin/bash
set -e

# Configuration
PROJECT_ID="moove-data-pipelines"
SERVICE_NAME="hdvi-folder-notifier"
REGION="us-central1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Get Slack webhook URL from Secret Manager (or set it manually)
# SLACK_WEBHOOK_URL should be stored in Secret Manager as "hdvi-folder-notifier-slack-webhook"
echo "🚀 Deploying ${SERVICE_NAME} to Cloud Run..."

# Build and push the container image
echo "📦 Building container image..."
gcloud builds submit \
  --project="${PROJECT_ID}" \
  --tag="${IMAGE_NAME}" \
  .

# Deploy to Cloud Run
echo "🚢 Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --image="${IMAGE_NAME}" \
  --region="${REGION}" \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="GCP_PROJECT=${PROJECT_ID}" \
  --set-secrets="SLACK_WEBHOOK_URL=hdvi-folder-notifier-slack-webhook:latest" \
  --memory=512Mi \
  --cpu=1 \
  --max-instances=10 \
  --min-instances=0 \
  --timeout=60 \
  --ingress=internal \
  --no-cpu-throttling

echo "✅ Deployment complete!"

# Get the service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format='value(status.url)')

echo ""
echo "📍 Service URL: ${SERVICE_URL}"
echo ""
echo "Next steps:"
echo "1. Create the Pub/Sub subscription using setup-pubsub.sh"
echo "2. Verify the Slack webhook secret is set up correctly"

