#!/bin/bash

# Helper script to view all notified folders in Firestore

PROJECT_ID="moove-data-pipelines"
COLLECTION="notified_folders"

echo "📁 Notified folders in Firestore:"
echo "=================================="
echo ""

# List all documents in the collection
gcloud firestore documents list "${COLLECTION}" \
  --project="${PROJECT_ID}" \
  --format="table(name,createTime)" \
  --sort-by="createTime"

echo ""
echo "To view details of a specific folder:"
echo "  gcloud firestore documents describe <folder_path> --project=${PROJECT_ID} --collection=${COLLECTION}"
echo ""

