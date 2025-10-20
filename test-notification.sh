#!/bin/bash
set -e

# Test script to send a test notification

PROJECT_ID="moove-data-pipelines"
TOPIC_NAME="hdvi-process-incoming"
BUCKET_NAME="moove-incoming-data-u7x4ty"

# Check if folder path is provided
if [ -z "$1" ]; then
  echo "Usage: ./test-notification.sh <folder_path>"
  echo ""
  echo "Example:"
  echo "  ./test-notification.sh Prebind/2024/10/20"
  echo "  ./test-notification.sh Postbind/test-batch-123"
  echo "  ./test-notification.sh test/validation"
  echo ""
  exit 1
fi

FOLDER_PATH="$1"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Create test message
MESSAGE=$(cat <<EOF
{
  "name": "${FOLDER_PATH}/test-file-$(date +%s).csv",
  "bucket": "${BUCKET_NAME}",
  "timeCreated": "${TIMESTAMP}",
  "updated": "${TIMESTAMP}",
  "size": "12345",
  "contentType": "text/csv"
}
EOF
)

echo "🧪 Testing HDVI Folder Notifier"
echo "================================"
echo ""
echo "Sending test message for: ${FOLDER_PATH}"
echo ""

# Publish message
gcloud pubsub topics publish "${TOPIC_NAME}" \
  --project="${PROJECT_ID}" \
  --message="${MESSAGE}"

echo ""
echo "✅ Test message published!"
echo ""
echo "Check your Slack channel for the notification."
echo "If this is the first file in the folder, you should receive a notification."
echo ""
echo "To view logs:"
echo "  gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=hdvi-folder-notifier' --project=${PROJECT_ID} --limit=20"
echo ""

