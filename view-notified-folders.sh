#!/bin/bash

# Helper script to view all notified folders in Firestore

PROJECT_ID="moove-data-pipelines"
COLLECTION="notified_folders"

echo "📁 Notified folders in Firestore:"
echo "=================================="
echo ""

# List all documents in the collection using REST API
echo "Querying Firestore for notified folders..."
gcloud firestore databases documents list \
  --project="${PROJECT_ID}" \
  --database="(default)" \
  --collection="${COLLECTION}" \
  --format="table(name,fields.folder_path.stringValue,fields.first_notification_time.stringValue,fields.notified_at.timestampValue)"

echo ""
echo "To view details of a specific folder:"
echo "  gcloud firestore documents describe <folder_path> --project=${PROJECT_ID} --collection=${COLLECTION}"
echo ""

