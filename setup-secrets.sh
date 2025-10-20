#!/bin/bash
set -e

# Configuration
PROJECT_ID="moove-data-pipelines"
SECRET_NAME="hdvi-folder-notifier-slack-webhook"

echo "🔐 Setting up secrets for HDVI Folder Notifier..."

# Check if user provided webhook URL
if [ -z "$1" ]; then
  echo ""
  echo "Usage: ./setup-secrets.sh <SLACK_WEBHOOK_URL>"
  echo ""
  echo "Example:"
  echo "  ./setup-secrets.sh https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
  echo ""
  exit 1
fi

SLACK_WEBHOOK_URL="$1"

# Enable Secret Manager API
echo "🔌 Ensuring Secret Manager API is enabled..."
gcloud services enable secretmanager.googleapis.com --project="${PROJECT_ID}"

# Create or update the secret
if gcloud secrets describe "${SECRET_NAME}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "📝 Secret '${SECRET_NAME}' already exists. Adding new version..."
  echo -n "${SLACK_WEBHOOK_URL}" | gcloud secrets versions add "${SECRET_NAME}" \
    --project="${PROJECT_ID}" \
    --data-file=-
else
  echo "📝 Creating secret '${SECRET_NAME}'..."
  echo -n "${SLACK_WEBHOOK_URL}" | gcloud secrets create "${SECRET_NAME}" \
    --project="${PROJECT_ID}" \
    --replication-policy="automatic" \
    --data-file=-
fi

# Grant the Cloud Run service account access to the secret
SERVICE_ACCOUNT="${PROJECT_ID}@appspot.gserviceaccount.com"

echo "🔐 Granting Cloud Run service account access to secret..."
gcloud secrets add-iam-policy-binding "${SECRET_NAME}" \
  --project="${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"

echo ""
echo "✅ Secret setup complete!"
echo ""
echo "Secret: ${SECRET_NAME}"
echo "Service Account: ${SERVICE_ACCOUNT}"

