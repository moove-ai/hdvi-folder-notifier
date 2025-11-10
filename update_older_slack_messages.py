#!/usr/bin/env python3
"""
Script to update Slack messages for older folders that are complete but haven't been updated.

This script:
1. Finds folders in folders_needing_check that are actually complete
2. Updates their Slack messages with completion status
3. Marks them as processing_complete=True
4. Removes them from folders_needing_check
"""

import os
import sys
from datetime import datetime
from google.cloud import firestore
from google.cloud import storage
from google.cloud.secretmanager import SecretManagerServiceClient
import requests

# Initialize clients
PROJECT_ID = os.environ.get("GCP_PROJECT", "moove-data-pipelines")
db = firestore.Client(project=PROJECT_ID)
storage_client = storage.Client(project=PROJECT_ID)

COLLECTION_NAME = "notified_folders"
NEEDS_CHECK_COLLECTION = "folders_needing_check"
BUCKET_NAME = os.environ.get("BUCKET_NAME", "moove-incoming-data-u7x4ty")
OUTGOING_BUCKET_NAME = os.environ.get("OUTGOING_BUCKET_NAME", "moove-outgoing-data-u7x4ty")
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL", "C09MKS35S74")

# Get Slack bot token from Secret Manager or environment
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
if not SLACK_BOT_TOKEN:
    try:
        secret_client = SecretManagerServiceClient()
        secret_name = f'projects/{PROJECT_ID}/secrets/hdvi-slack-notifier-bot-token/versions/latest'
        response = secret_client.access_secret_version(request={'name': secret_name})
        SLACK_BOT_TOKEN = response.payload.data.decode('UTF-8')
        print("✅ Retrieved SLACK_BOT_TOKEN from Secret Manager")
    except Exception as e:
        print(f"❌ Failed to get SLACK_BOT_TOKEN from Secret Manager: {e}")
        print("   Set SLACK_BOT_TOKEN environment variable or ensure secret exists")
        sys.exit(1)


def get_outgoing_folder_path(folder_path: str) -> str:
    """Derive outgoing folder path from incoming folder path."""
    # Remove bucket prefix if present
    if folder_path.startswith(f"{BUCKET_NAME}/"):
        folder_path = folder_path[len(f"{BUCKET_NAME}/"):]
    # Add contextualized prefix
    return f"contextualized/{folder_path}"


def get_folder_stats(folder_path: str, bucket_name: str) -> tuple[int, int]:
    """Get file count and total size for a folder in GCS."""
    try:
        bucket = storage_client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=f"{folder_path}/")
        file_count = 0
        total_size = 0
        for blob in blobs:
            if blob.name.endswith(".jsonl.gz"):
                file_count += 1
                total_size += blob.size or 0
        return file_count, total_size
    except Exception as e:
        print(f"  ⚠️  Error getting stats for {folder_path}: {e}")
        return 0, 0


def round_timestamp_to_second(iso_timestamp: str) -> str:
    """Round an ISO timestamp to the nearest second."""
    if not iso_timestamp or iso_timestamp == "Unknown":
        return iso_timestamp
    try:
        from datetime import timedelta
        timestamp_clean = iso_timestamp.replace("Z", "+00:00")
        dt = datetime.fromisoformat(timestamp_clean)
        if dt.microsecond >= 500000:
            dt = dt.replace(microsecond=0) + timedelta(seconds=1)
        else:
            dt = dt.replace(microsecond=0)
        result = dt.isoformat()
        if result.endswith("+00:00"):
            result = result.replace("+00:00", "Z")
        return result
    except (ValueError, AttributeError):
        return iso_timestamp


def format_time_difference(first_time: str, last_time: str) -> str:
    """Calculate and format the time difference between two ISO timestamps."""
    if not first_time or first_time == "Unknown" or not last_time:
        return "Unknown"
    try:
        from datetime import timedelta
        first_clean = first_time.replace("Z", "+00:00")
        last_clean = last_time.replace("Z", "+00:00")
        first_dt = datetime.fromisoformat(first_clean)
        last_dt = datetime.fromisoformat(last_clean)
        diff = last_dt - first_dt
        total_seconds = int(round(diff.total_seconds()))
        
        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m {seconds}s"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"
        else:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            return f"{days}d {hours}h"
    except (ValueError, AttributeError, TypeError):
        return "Unknown"


def format_size(size_bytes: int) -> str:
    """Format size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def update_slack_message(folder_path: str, file_count: int, total_size: int, check_time: str, first_time: str):
    """Update Slack message with completion status."""
    # Round timestamps
    first_time_rounded = round_timestamp_to_second(first_time)
    check_time_rounded = round_timestamp_to_second(check_time)
    time_diff = format_time_difference(first_time_rounded, check_time_rounded)
    
    size_str = format_size(total_size)
    
    fields = [
        {"type": "mrkdwn", "text": f"*Folder:*\n`{BUCKET_NAME}/{folder_path}`"},
        {"type": "mrkdwn", "text": f"*First File Time:*\n{first_time_rounded}"},
        {"type": "mrkdwn", "text": f"*JSONL.GZ Files:*\n{file_count}"},
        {"type": "mrkdwn", "text": f"*Total Size:*\n{size_str}"},
        {"type": "mrkdwn", "text": f"*Processing Status:*\n✅ Complete (0 files remaining)"},
        {"type": "mrkdwn", "text": f"*Last Check:*\n{check_time_rounded}"},
    ]
    
    if time_diff and time_diff != "Unknown":
        fields.append({"type": "mrkdwn", "text": f"*Duration:*\n{time_diff}"})
    
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
    
    url = "https://slack.com/api/chat.update"
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json;charset=utf-8",
    }
    
    # Get Slack message info from Firestore
    doc_id = folder_path.replace("/", "_").replace("\\", "_")
    doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        print(f"  ⚠️  Folder {folder_path} not found in notified_folders")
        return False
    
    data = doc.to_dict() or {}
    ts = data.get("slack_message_ts")
    channel = data.get("slack_channel") or SLACK_CHANNEL
    
    if not ts:
        print(f"  ⚠️  No Slack message TS found for {folder_path}")
        return False
    
    payload = {
        "channel": channel,
        "ts": ts,
        "text": f"Folder complete: {BUCKET_NAME}/{folder_path}",
        "blocks": blocks,
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        if not result.get("ok"):
            print(f"  ❌ Slack API error: {result}")
            return False
        return True
    except Exception as e:
        print(f"  ❌ Error updating Slack message: {e}")
        return False


def update_older_slack_messages():
    """Update Slack messages for older folders that are complete."""
    print(f"🔍 Checking folders in {NEEDS_CHECK_COLLECTION}...")
    
    query = db.collection(NEEDS_CHECK_COLLECTION).limit(100)
    docs = list(query.stream())
    
    print(f"📊 Found {len(docs)} folders to check")
    
    updated_count = 0
    already_complete_count = 0
    not_complete_count = 0
    error_count = 0
    
    for doc in docs:
        try:
            data = doc.to_dict()
            folder_path = data.get("folder_path", "")
            
            if not folder_path:
                continue
            
            print(f"\n📁 Checking: {folder_path}")
            
            # Count actual incoming files (not the stored count, which may be outdated)
            incoming_bucket = storage_client.bucket(BUCKET_NAME)
            incoming_blobs = list(incoming_bucket.list_blobs(prefix=f"{folder_path}/"))
            incoming_file_count = sum(1 for b in incoming_blobs if b.name.endswith(".jsonl.gz"))
            
            if incoming_file_count == 0:
                print(f"  ⏭️  Skipping (no incoming files found)")
                continue
            
            # Check outgoing folder
            outgoing_folder_path = get_outgoing_folder_path(folder_path)
            outgoing_file_count, _ = get_folder_stats(outgoing_folder_path, OUTGOING_BUCKET_NAME)
            processing_diff = incoming_file_count - outgoing_file_count
            
            stored_count = data.get("file_count", 0)
            print(f"  📊 Stored count: {stored_count}, Actual incoming: {incoming_file_count}, Outgoing: {outgoing_file_count}, Diff: {processing_diff}")
            
            if processing_diff == 0:
                # Processing is complete - update Slack message
                print(f"  ✅ Processing complete, updating Slack message...")
                
                # Get folder info from main collection
                doc_id = folder_path.replace("/", "_").replace("\\", "_")
                main_doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
                main_doc = main_doc_ref.get()
                
                if not main_doc.exists:
                    print(f"  ⚠️  Folder not found in main collection")
                    error_count += 1
                    continue
                
                main_data = main_doc.to_dict() or {}
                first_time = main_data.get("first_notification_time") or "Unknown"
                # Calculate actual total size from incoming files
                total_size = sum(b.size or 0 for b in incoming_blobs if b.name.endswith(".jsonl.gz"))
                check_time = datetime.utcnow().isoformat()
                
                # Update Slack message
                if update_slack_message(folder_path, incoming_file_count, total_size, check_time, first_time):
                    print(f"  ✅ Slack message updated")
                    
                    # Mark as complete in main collection
                    main_doc_ref.update({"processing_complete": True})
                    
                    # Remove from folders_needing_check
                    needs_check_ref = db.collection(NEEDS_CHECK_COLLECTION).document(doc.id)
                    needs_check_ref.delete()
                    
                    updated_count += 1
                else:
                    error_count += 1
            else:
                print(f"  ⏳ Still processing ({processing_diff} files remaining)")
                not_complete_count += 1
                
        except Exception as e:
            print(f"  ❌ Error processing {doc.id}: {e}")
            error_count += 1
            continue
    
    print("\n📊 Summary:")
    print(f"  ✅ Updated Slack messages: {updated_count}")
    print(f"  ⏳ Still processing: {not_complete_count}")
    print(f"  ❌ Errors: {error_count}")
    print(f"\n✨ Done!")


if __name__ == "__main__":
    try:
        update_older_slack_messages()
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

