#!/bin/bash
set -e

# Configuration
PROJECT_ID="moove-data-pipelines"
TOPIC_NAME="hdvi-process-incoming"
SUBSCRIPTION_NAME="hdvi-folder-notifier-sub"
SERVICE_NAME="hdvi-folder-notifier"
REGION="us-central1"

echo "🔧 Setting up Pub/Sub subscription for ${SERVICE_NAME}..."

# Get the Cloud Run service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format='value(status.url)' 2>/dev/null || echo "")

if [ -z "${SERVICE_URL}" ]; then
  echo "❌ Error: Cloud Run service '${SERVICE_NAME}' not found in region '${REGION}'"
  echo "Please deploy the service first using ./deploy.sh"
  exit 1
fi

echo "📍 Service URL: ${SERVICE_URL}"

# Create service account for Pub/Sub to invoke Cloud Run
SA_NAME="${SERVICE_NAME}-invoker"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "👤 Creating service account for Pub/Sub invoker..."
if ! gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SA_NAME}" \
    --project="${PROJECT_ID}" \
    --display-name="HDVI Folder Notifier Pub/Sub Invoker"
else
  echo "   Service account already exists"
fi

# Grant the service account permission to invoke the Cloud Run service
echo "🔐 Granting Cloud Run Invoker permission..."
gcloud run services add-iam-policy-binding "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.invoker"

# Check if subscription already exists
if gcloud pubsub subscriptions describe "${SUBSCRIPTION_NAME}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "⚠️  Subscription '${SUBSCRIPTION_NAME}' already exists. Deleting and recreating..."
  gcloud pubsub subscriptions delete "${SUBSCRIPTION_NAME}" --project="${PROJECT_ID}" --quiet
fi

# Create the Pub/Sub push subscription
echo "📮 Creating Pub/Sub subscription..."
gcloud pubsub subscriptions create "${SUBSCRIPTION_NAME}" \
  --project="${PROJECT_ID}" \
  --topic="${TOPIC_NAME}" \
  --push-endpoint="${SERVICE_URL}/" \
  --push-auth-service-account="${SA_EMAIL}" \
  --ack-deadline=60 \
  --message-retention-duration=7d

echo ""
echo "✅ Setup complete!"
echo ""
echo "Configuration:"
echo "  Project: ${PROJECT_ID}"
echo "  Topic: ${TOPIC_NAME}"
echo "  Subscription: ${SUBSCRIPTION_NAME}"
echo "  Service URL: ${SERVICE_URL}"
echo "  Service Account: ${SA_EMAIL}"
echo ""
echo "The service will now receive messages from the '${TOPIC_NAME}' topic."

