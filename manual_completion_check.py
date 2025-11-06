#!/usr/bin/env python3
"""Manually check and update completion status for a folder."""
import os
import sys
from google.cloud import storage
from google.cloud import firestore
import requests

PROJECT_ID = os.environ.get("GCP_PROJECT", "moove-data-pipelines")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "moove-incoming-data-u7x4ty")
OUTGOING_BUCKET_NAME = os.environ.get("OUTGOING_BUCKET_NAME", "moove-outgoing-data-u7x4ty")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL", "")

storage_client = storage.Client(project=PROJECT_ID)
db = firestore.Client(project=PROJECT_ID)

def get_folder_stats(folder_path: str, bucket_name: str):
    """Get file count and total size for a folder."""
    prefix = f"{folder_path}/" if not folder_path.endswith("/") else folder_path
    blobs = storage_client.list_blobs(bucket_name, prefix=prefix)
    
    jsonl_gz_count = 0
    total_size = 0
    for blob in blobs:
        if not blob.name.endswith('/') and blob.name.endswith('.jsonl.gz'):
            jsonl_gz_count += 1
            total_size += blob.size
    
    return jsonl_gz_count, total_size

def format_size(size_bytes: int) -> str:
    """Format size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def update_slack_message(folder_path: str, file_count: int, total_size: int, processing_diff: int, check_time: str):
    """Update Slack message with completion status."""
    if not SLACK_BOT_TOKEN or not SLACK_CHANNEL:
        print("SLACK_BOT_TOKEN and SLACK_CHANNEL must be set")
        return False
    
    doc_id = folder_path.replace("/", "_").replace("\\", "_")
    doc_ref = db.collection("notified_folders").document(doc_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        print(f"Folder {folder_path} not found in Firestore")
        return False
    
    data = doc.to_dict() or {}
    ts = data.get("slack_message_ts")
    channel = data.get("slack_channel") or SLACK_CHANNEL
    first_time = data.get("first_notification_time") or "Unknown"
    
    if not ts:
        print(f"No Slack message TS found for folder {folder_path}")
        return False
    
    size_str = format_size(total_size)
    
    fields = [
        {"type": "mrkdwn", "text": f"*Folder:*\n`{BUCKET_NAME}/{folder_path}`"},
        {"type": "mrkdwn", "text": f"*First File Time:*\n{first_time}"},
        {"type": "mrkdwn", "text": f"*JSONL.GZ Files:*\n{file_count}"},
        {"type": "mrkdwn", "text": f"*Total Size:*\n{size_str}"},
    ]
    
    if processing_diff == 0:
        fields.append({"type": "mrkdwn", "text": f"*Processing Status:*\n✅ Complete (0 files remaining)"})
    else:
        fields.append({"type": "mrkdwn", "text": f"*Processing Status:*\n⏳ {processing_diff} files remaining"})
    
    if check_time:
        fields.append({"type": "mrkdwn", "text": f"*Last Check:*\n{check_time}"})
    
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📁 New HDVI Data Folder"},
        },
        {
            "type": "section",
            "fields": fields,
        },
    ]
    
    url = f"https://slack.com/api/chat.update"
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json;charset=utf-8",
    }
    payload = {
        "channel": channel,
        "ts": ts,
        "text": f"Folder complete: {BUCKET_NAME}/{folder_path}",
        "blocks": blocks,
    }
    
    resp = requests.post(url, headers=headers, json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack API error: {data}")
    
    print(f"Updated Slack message for {folder_path}: diff={processing_diff}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 manual_completion_check.py <folder_path>")
        print("Example: python3 manual_completion_check.py Prebind/conn_01K9D5RXB79N3M0AYHFQ89HQ6J")
        sys.exit(1)
    
    folder_path = sys.argv[1]
    
    # Get incoming stats
    incoming_count, incoming_size = get_folder_stats(folder_path, BUCKET_NAME)
    print(f"Incoming: {incoming_count} files, {format_size(incoming_size)}")
    
    # Get outgoing stats
    outgoing_folder_path = f"contextualized/{folder_path}"
    outgoing_count, _ = get_folder_stats(outgoing_folder_path, OUTGOING_BUCKET_NAME)
    print(f"Outgoing: {outgoing_count} files")
    
    processing_diff = incoming_count - outgoing_count
    print(f"Difference: {processing_diff}")
    
    # Update Firestore with current stats if needed
    doc_id = folder_path.replace("/", "_").replace("\\", "_")
    doc_ref = db.collection("notified_folders").document(doc_id)
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.update({
            "file_count": incoming_count,
            "total_size_bytes": incoming_size,
        })
    
    # Update Slack message
    from datetime import datetime
    check_time = datetime.utcnow().isoformat()
    update_slack_message(folder_path, incoming_count, incoming_size, processing_diff, check_time)

