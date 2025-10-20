#!/bin/bash

# Helper script to view Cloud Run logs

PROJECT_ID="moove-data-pipelines"
SERVICE_NAME="hdvi-folder-notifier"

# Get limit from argument or default to 50
LIMIT="${1:-50}"

echo "📋 Viewing last ${LIMIT} log entries for ${SERVICE_NAME}..."
echo ""

gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --limit="${LIMIT}" \
  --format="table(timestamp,severity,textPayload)" \
  --order="desc"

