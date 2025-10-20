#!/bin/bash
set -e

# Configuration
PROJECT_ID="moove-data-pipelines"
COLLECTION_NAME="notified_folders"

echo "🔧 Setting up Firestore for HDVI Folder Notifier..."

# Enable Firestore API
echo "🔌 Ensuring Firestore API is enabled..."
gcloud services enable firestore.googleapis.com --project="${PROJECT_ID}"

# Check if Firestore is already set up
echo "📊 Checking Firestore database..."
DATABASE_INFO=$(gcloud firestore databases describe --project="${PROJECT_ID}" 2>/dev/null || echo "")

if [ -z "${DATABASE_INFO}" ]; then
  echo ""
  echo "⚠️  Firestore database not found in project '${PROJECT_ID}'"
  echo ""
  echo "You need to create a Firestore database first. Run:"
  echo ""
  echo "  gcloud firestore databases create \\"
  echo "    --project=${PROJECT_ID} \\"
  echo "    --location=us-central1 \\"
  echo "    --type=firestore-native"
  echo ""
  exit 1
else
  echo "✅ Firestore database already exists"
fi

# Grant the Cloud Run service account access to Firestore
SERVICE_ACCOUNT="${PROJECT_ID}@appspot.gserviceaccount.com"

echo "🔐 Granting Cloud Run service account Firestore access..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/datastore.user"

echo ""
echo "✅ Firestore setup complete!"
echo ""
echo "Collection: ${COLLECTION_NAME}"
echo "Service Account: ${SERVICE_ACCOUNT}"
echo ""
echo "The service will use this collection to track which folders have been notified."

