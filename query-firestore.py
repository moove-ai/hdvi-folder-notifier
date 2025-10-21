#!/usr/bin/env python3

import os
from google.cloud import firestore

# Initialize Firestore client
db = firestore.Client(project="moove-data-pipelines")

# Query the notified_folders collection
collection_ref = db.collection("notified_folders")
docs = collection_ref.stream()

print("📁 Notified folders in Firestore:")
print("==================================")
print()

for doc in docs:
    data = doc.to_dict()
    print(f"Document ID: {doc.id}")
    print(f"  Folder Path: {data.get('folder_path', 'N/A')}")
    print(f"  First Notification Time: {data.get('first_notification_time', 'N/A')}")
    print(f"  Notified At: {data.get('notified_at', 'N/A')}")
    print()

if not any(docs):
    print("No documents found in the collection.")
