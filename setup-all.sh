#!/bin/bash
set -e

# Master setup script for HDVI Folder Notifier
# This script orchestrates the complete setup process

echo "🚀 HDVI Folder Notifier - Complete Setup"
echo "=========================================="
echo ""

# Check if Slack webhook URL is provided
if [ -z "$1" ]; then
  echo "❌ Error: Slack webhook URL required"
  echo ""
  echo "Usage: ./setup-all.sh <SLACK_WEBHOOK_URL>"
  echo ""
  echo "Example:"
  echo "  ./setup-all.sh https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
  echo ""
  exit 1
fi

SLACK_WEBHOOK_URL="$1"
PROJECT_ID="moove-data-pipelines"

# Confirm project
echo "📋 Project: ${PROJECT_ID}"
echo ""
read -p "Continue with this project? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Cancelled."
  exit 1
fi

# Step 1: Set up secrets
echo ""
echo "Step 1/4: Setting up secrets..."
echo "================================"
./setup-secrets.sh "${SLACK_WEBHOOK_URL}"

# Step 2: Set up Firestore
echo ""
echo "Step 2/4: Setting up Firestore..."
echo "=================================="
./setup-firestore.sh

# Step 3: Deploy Cloud Run service
echo ""
echo "Step 3/4: Deploying Cloud Run service..."
echo "========================================="
./deploy.sh

# Step 4: Set up Pub/Sub subscription
echo ""
echo "Step 4/4: Setting up Pub/Sub subscription..."
echo "============================================="
./setup-pubsub.sh

# Complete
echo ""
echo "=========================================="
echo "✅ Setup complete!"
echo "=========================================="
echo ""
echo "Your HDVI Folder Notifier is now running and will send Slack"
echo "notifications when new folders are detected in:"
echo "  - moove-incoming-data-u7x4ty/Prebind/"
echo "  - moove-incoming-data-u7x4ty/Postbind/"
echo "  - moove-incoming-data-u7x4ty/test/"
echo ""
echo "To test the service, you can:"
echo "  ./test-notification.sh Prebind/2024/10/20"
echo ""
echo "To view logs:"
echo "  gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=hdvi-folder-notifier' --project=${PROJECT_ID} --limit=20"
echo ""

