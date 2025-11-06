import base64
import csv
import json
import os
import logging
import threading
import time
from datetime import datetime
from io import StringIO
from typing import Dict, Tuple
from flask import Flask, request, jsonify
import requests
from google.cloud import firestore
from google.cloud import storage

# Configure logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT", "moove-data-pipelines")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL", "")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "moove-incoming-data-u7x4ty")
OUTGOING_BUCKET_NAME = os.environ.get("OUTGOING_BUCKET_NAME", "moove-outgoing-data-u7x4ty")
MONITORED_PREFIXES = os.environ.get("MONITORED_PREFIXES", "Prebind/,Postbind/,test/").split(",")

# Optional analytics CSV sink in GCS
ANALYTICS_BUCKET = os.environ.get("ANALYTICS_BUCKET", "")
ANALYTICS_OBJECT = os.environ.get("ANALYTICS_OBJECT", "")

# Initialize Firestore to track notified folders
db = firestore.Client(project=PROJECT_ID)
COLLECTION_NAME = "notified_folders"

# Initialize GCS client
storage_client = storage.Client(project=PROJECT_ID)
bucket_client = storage_client.bucket(BUCKET_NAME)

# Folder monitoring state
# Maps folder_path -> {"last_update": datetime, "known_files": set, "monitoring_thread": Thread, "processing_thread": Thread, "incoming_file_count": int}
monitored_folders: Dict[str, Dict] = {}
monitored_folders_lock = threading.Lock()

# Monitoring configuration
CHECK_INTERVAL_SECONDS = 15
INACTIVITY_TIMEOUT_SECONDS = 60
PROCESSING_CHECK_INTERVAL_SECONDS = 60  # Check processing progress every minute


def _update_slack_metadata_with_retry(doc_id: str, ts: str, channel: str, retries: int = 3) -> None:
    """Best-effort save of Slack message identifiers to Firestore to enable later edits."""
    last_err = None
    for _ in range(retries):
        try:
            doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
            doc_ref.update({
                "slack_message_ts": ts,
                "slack_channel": channel,
            })
            return
        except Exception as e:
            last_err = e
            time.sleep(0.2)
    if last_err:
        logger.error(f"Failed to save Slack message metadata after retries for doc {doc_id}: {last_err}")


def get_folder_from_path(file_path: str) -> str:
    """
    Extract the specific subfolder from a file path within monitored prefixes.
    Only returns a subfolder if there actually is one.
    Example: test/subfolder/file.csv -> test/subfolder
    Example: test/file.csv -> test (no subfolder)
    """
    # Find which monitored prefix this file belongs to
    for prefix in MONITORED_PREFIXES:
        if file_path.startswith(prefix):
            # Remove the prefix and get the next path component (subfolder)
            # Normalize to ensure we don't create double slashes later
            norm_prefix = prefix.rstrip('/')
            relative_path = file_path[len(prefix):].lstrip('/')
            if relative_path:
                # Get the first path component after the prefix
                subfolder = relative_path.split('/')[0]
                # Only return subfolder if it's not a file (has no extension or is a directory)
                if '.' not in subfolder or subfolder.count('/') > 0:
                    return f"{norm_prefix}/{subfolder.strip('/')}"
            # If no subfolder or it's a file directly in the prefix, return just the prefix
            return norm_prefix
    return ""


def is_monitored_path(file_path: str) -> bool:
    """Check if the file path starts with one of the monitored prefixes."""
    return any(file_path.startswith(prefix) for prefix in MONITORED_PREFIXES)


@firestore.transactional
def check_and_mark_folder(transaction, folder_path: str, timestamp: str) -> bool:
    """
    Atomically check if folder has been notified and mark it if not.
    Returns True if this is a new folder (should notify), False otherwise.
    """
    # Encode folder path to make it a valid Firestore document ID
    doc_id = folder_path.replace("/", "_").replace("\\", "_")
    doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
    doc = doc_ref.get(transaction=transaction)
    
    if doc.exists:
        return False  # Already notified
    
    # Mark as notified within the same transaction
    transaction.set(
        doc_ref,
        {
            "folder_path": folder_path,
            "doc_id": doc_id,
            "first_notification_time": timestamp,
            "notified_at": firestore.SERVER_TIMESTAMP,
            # Slack message linkage (optional, when using Slack Web API)
            "slack_message_ts": None,
            "slack_channel": SLACK_CHANNEL or None,
        },
    )
    return True  # New folder, should notify


@firestore.transactional
def check_and_mark_final(transaction, folder_path: str, file_count: int, total_size: int) -> bool:
    """
    Atomically check if final notification was already sent; if not, mark it with stats.
    Returns True if we should send final notification/edit now, False otherwise.
    """
    doc_id = folder_path.replace("/", "_").replace("\\", "_")
    doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
    doc = doc_ref.get(transaction=transaction)
    data = doc.to_dict() or {}
    if doc.exists and data.get("final_notification_sent"):
        return False

    # Mark final as sent and store stats
    transaction.set(
        doc_ref,
        {
            "folder_path": folder_path,
            "doc_id": doc_id,
            "final_notification_sent": True,
            "final_notification_time": firestore.SERVER_TIMESTAMP,
            "file_count": file_count,
            "total_size_bytes": total_size,
        },
        merge=True,
    )
    return True


def _slack_api_post(path: str, payload: Dict) -> Dict:
    url = f"https://slack.com/api/{path}"
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json;charset=utf-8",
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack API error for {path}: {data}")
    return data


def send_slack_notification(folder_path: str, timestamp: str) -> bool:
    """Send initial notification to Slack. If bot token/channel are set, use chat.postMessage and store ts; else fallback to webhook."""
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📁 New HDVI Data Folder"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Folder:*\n`{BUCKET_NAME}/{folder_path}`"},
                {"type": "mrkdwn", "text": f"*First File Time:*\n{timestamp}"},
            ],
        },
    ]

    # Prefer Slack Web API when configured
    if SLACK_BOT_TOKEN and SLACK_CHANNEL:
        try:
            res = _slack_api_post(
                "chat.postMessage",
                {
                    "channel": SLACK_CHANNEL,
                    "text": f"New folder: {BUCKET_NAME}/{folder_path}",
                    "blocks": blocks,
                },
            )
            ts = res.get("ts")
            channel = res.get("channel") or SLACK_CHANNEL
            doc_id = folder_path.replace("/", "_").replace("\\", "_")
            if ts and channel:
                _update_slack_metadata_with_retry(doc_id, ts, channel)
            logger.info(f"Slack message posted with ts={ts} channel={channel} for folder: {folder_path}")
            return True
        except Exception as e:
            # Do NOT fallback to webhook when bot token is configured; avoid duplicate messages
            logger.error(f"Failed Slack Web API post: {e}")
            return False

    # Fallback to webhook (cannot edit later) only when bot token not configured
    if SLACK_BOT_TOKEN:
        # Bot is configured but post failed above; do not send webhook fallback
        return False
    if not SLACK_WEBHOOK_URL:
        logger.warning("SLACK_WEBHOOK_URL not configured, skipping webhook notification")
        return False

    message = {"text": f"🆕 New folder detected in HDVI data", "blocks": blocks}
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=message, timeout=10)
        response.raise_for_status()
        logger.info(f"Slack notification sent for folder: {folder_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to send Slack notification via webhook: {e}")
        return False


def get_outgoing_folder_path(incoming_folder_path: str) -> str:
    """
    Convert incoming folder path to outgoing folder path.
    Pattern: {incoming_folder} -> contextualized/{incoming_folder}
    Example: test/subfolder -> contextualized/test/subfolder
    """
    return f"contextualized/{incoming_folder_path}"


def get_folder_stats(folder_path: str, bucket_name: str = None) -> Tuple[int, int]:
    """
    Get statistics for a folder.
    Returns: (count of jsonl.gz files, total size in bytes)
    """
    if bucket_name is None:
        bucket_name = BUCKET_NAME
    try:
        # List all blobs with the folder prefix (use client-level listing for robustness)
        prefix = f"{folder_path}/" if not folder_path.endswith("/") else folder_path
        logger.info(f"Listing blobs for stats: bucket={bucket_name} prefix={prefix}")
        blobs = storage_client.list_blobs(bucket_name, prefix=prefix)

        jsonl_gz_count = 0
        total_size = 0
        scanned = 0

        for blob in blobs:
            scanned += 1
            # Count any files anywhere under the folder (including subfolders)
            if not blob.name.endswith('/') and blob.name.endswith('.jsonl.gz'):
                jsonl_gz_count += 1
                total_size += blob.size
        logger.info(f"Folder stats listing complete: scanned={scanned} matched_jsonl_gz={jsonl_gz_count} total_size={total_size}")
        
        return jsonl_gz_count, total_size
    except Exception as e:
        logger.error(f"Error getting folder stats for {folder_path}: {e}")
        return 0, 0


def format_size(size_bytes: int) -> str:
    """Format size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def send_final_slack_notification(folder_path: str, file_count: int, total_size: int, processing_diff: int = None, check_time: str = None) -> bool:
    """Edit the original Slack message with final statistics when possible; else send a second message via webhook."""
    size_str = format_size(total_size)
    
    # Retrieve first notification time from Firestore to preserve original message fields
    doc_id = folder_path.replace("/", "_").replace("\\", "_")
    doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
    doc = doc_ref.get()
    data = doc.to_dict() or {}
    first_time = data.get("first_notification_time") or "Unknown"
    
    # Build fields list
    fields = [
        {"type": "mrkdwn", "text": f"*Folder:*\n`{BUCKET_NAME}/{folder_path}`"},
        {"type": "mrkdwn", "text": f"*First File Time:*\n{first_time}"},
        {"type": "mrkdwn", "text": f"*JSONL.GZ Files:*\n{file_count}"},
        {"type": "mrkdwn", "text": f"*Total Size:*\n{size_str}"},
    ]
    
    # Add processing progress if provided
    if processing_diff is not None:
        if processing_diff == 0:
            fields.append({"type": "mrkdwn", "text": f"*Processing Status:*\n✅ Complete (0 files remaining)"})
        else:
            fields.append({"type": "mrkdwn", "text": f"*Processing Status:*\n⏳ {processing_diff} files remaining"})
    
    if check_time:
        fields.append({"type": "mrkdwn", "text": f"*Last Check:*\n{check_time}"})
    
    # Keep original title and add statistics
    final_blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📁 New HDVI Data Folder"},
        },
        {
            "type": "section",
            "fields": fields,
        },
    ]

    # Prefer editing the original message when token/channel + ts exist
    if SLACK_BOT_TOKEN:
        try:
            ts = (doc.exists and data.get("slack_message_ts")) or None
            channel = (doc.exists and data.get("slack_channel")) or SLACK_CHANNEL
            logger.info(f"Preparing Slack edit: doc_exists={doc.exists} ts={ts} channel={channel} doc_id={doc_id}")
            if ts and channel:
                _slack_api_post(
                    "chat.update",
                    {
                        "channel": channel,
                        "ts": ts,
                        "text": f"Folder complete: {BUCKET_NAME}/{folder_path}",
                        "blocks": final_blocks,
                    },
                )
                logger.info(f"Edited Slack message ts={ts} channel={channel} for folder: {folder_path} with file_count={file_count} total_size={total_size} processing_diff={processing_diff}")
                return True
            else:
                logger.warning(f"Cannot edit Slack message: missing ts/channel for folder {folder_path}")
        except Exception as e:
            # Do NOT fallback to webhook when bot token is configured; avoid double messages
            logger.error(f"Failed to edit Slack message: {e}")
            return False

    # Fallback: only when no bot token configured
    if not SLACK_BOT_TOKEN and SLACK_WEBHOOK_URL:
        try:
            message = {"text": f"✅ Folder upload complete: {folder_path}", "blocks": final_blocks}
            response = requests.post(SLACK_WEBHOOK_URL, json=message, timeout=10)
            response.raise_for_status()
            logger.info(f"Final Slack notification sent (webhook) for folder: {folder_path} with file_count={file_count} total_size={total_size}")
            return True
        except Exception as e:
            logger.error(f"Failed to send final Slack notification via webhook: {e}")
            return False

    logger.warning("No Slack mechanism configured for final notification")
    return False


def _append_completion_csv(folder_path: str, first_time: str, final_time_iso: str, file_count: int, total_size: int) -> None:
    """Append a CSV row to GCS object with folder completion stats. Best-effort with generation precondition retries."""
    if not ANALYTICS_BUCKET or not ANALYTICS_OBJECT:
        return

    try:
        bucket = storage_client.bucket(ANALYTICS_BUCKET)
        blob = bucket.blob(ANALYTICS_OBJECT)

        # Build row via csv writer
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow([folder_path, first_time or "", final_time_iso, str(file_count), str(total_size)])
        row_bytes = buf.getvalue()

        # Try to check if object exists, but handle errors gracefully
        object_exists = False
        try:
            object_exists = blob.exists()
        except Exception as e:
            logger.warning(f"Could not check CSV existence for {folder_path}: {e}, assuming new file")
            object_exists = False

        # If object does not exist, write header + row
        if not object_exists:
            try:
                header_buf = StringIO()
                writer_h = csv.writer(header_buf)
                writer_h.writerow(["folder_path", "first_notification_time", "final_notification_time", "file_count", "total_size_bytes"])
                data = header_buf.getvalue() + row_bytes
                blob.upload_from_string(data, content_type="text/csv")
                logger.info(f"Created analytics CSV with first row for {folder_path} at {ANALYTICS_BUCKET}/{ANALYTICS_OBJECT}")
                return
            except Exception as e:
                logger.error(f"Failed to create analytics CSV for {folder_path}: {e}")
                return

        # Else: read-modify-write with generation precondition
        retries = 3
        for attempt in range(retries):
            try:
                blob.reload()
                gen = blob.generation
                existing = blob.download_as_text()
                new_data = existing + row_bytes
                blob.upload_from_string(new_data, content_type="text/csv", if_generation_match=gen)
                logger.info(f"Appended analytics CSV row for {folder_path} to {ANALYTICS_BUCKET}/{ANALYTICS_OBJECT}")
                return
            except Exception as e:
                if attempt < retries - 1:
                    logger.debug(f"Retrying CSV append for {folder_path} (attempt {attempt + 1}/{retries}): {e}")
                    time.sleep(0.2)
                    continue
                logger.error(f"Failed to append analytics CSV for {folder_path} after {retries} attempts: {e}")
                return
    except Exception as e:
        logger.error(f"Analytics CSV error for {folder_path}: {e}", exc_info=True)


def check_folder_for_new_files(folder_path: str) -> bool:
    """
    Check if there are new files in the folder since last check.
    Returns True if new files were found, False otherwise.
    """
    try:
        prefix = f"{folder_path}/" if not folder_path.endswith("/") else folder_path
        logger.debug(f"Checking folder for new files: bucket={BUCKET_NAME} prefix={prefix}")
        blobs = storage_client.list_blobs(BUCKET_NAME, prefix=prefix)
        
        with monitored_folders_lock:
            if folder_path not in monitored_folders:
                return False
            
            known_files = monitored_folders[folder_path]["known_files"]
            found_new = False
            
            scanned = 0
            for blob in blobs:
                scanned += 1
                # Consider any non-directory blob under the prefix
                if not blob.name.endswith('/'):
                    if blob.name not in known_files:
                        known_files.add(blob.name)
                        found_new = True
                        logger.debug(f"New file detected in {folder_path}: {blob.name}")
            
            if found_new:
                monitored_folders[folder_path]["last_update"] = datetime.utcnow()
            else:
                logger.debug(f"No new files found. scanned={scanned} known_files={len(known_files)}")
            
            return found_new
    except Exception as e:
        logger.error(f"Error checking folder {folder_path} for new files: {e}")
        return False


def monitor_processing_progress(folder_path: str, incoming_file_count: int):
    """
    Monitor processing progress by comparing incoming and outgoing folder file counts.
    Updates Slack message every minute with the difference.
    Stops when difference is 0.
    """
    logger.info(f"Starting processing progress monitoring for folder: {folder_path} (incoming files: {incoming_file_count})")
    outgoing_folder_path = get_outgoing_folder_path(folder_path)
    
    try:
        while True:
            time.sleep(PROCESSING_CHECK_INTERVAL_SECONDS)
            
            with monitored_folders_lock:
                if folder_path not in monitored_folders:
                    logger.info(f"Folder {folder_path} removed from processing monitoring")
                    break
            
            # Get outgoing folder file count
            outgoing_file_count, _ = get_folder_stats(outgoing_folder_path, OUTGOING_BUCKET_NAME)
            processing_diff = incoming_file_count - outgoing_file_count
            check_time = datetime.utcnow().isoformat()
            
            logger.info(f"Processing progress for {folder_path}: incoming={incoming_file_count} outgoing={outgoing_file_count} diff={processing_diff}")
            
            # Update Slack message with progress
            # Get total size from Firestore or recalculate
            doc_id = folder_path.replace("/", "_").replace("\\", "_")
            doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
            doc = doc_ref.get()
            data = doc.to_dict() or {}
            total_size = data.get("total_size_bytes", 0)
            
            send_final_slack_notification(folder_path, incoming_file_count, total_size, processing_diff, check_time)
            
            # Stop monitoring if all files are processed
            if processing_diff == 0:
                logger.info(f"All files processed for {folder_path}, stopping processing monitoring")
                with monitored_folders_lock:
                    monitored_folders.pop(folder_path, None)
                break
                
    except Exception as e:
        logger.error(f"Error in processing progress monitoring thread for {folder_path}: {e}", exc_info=True)
        with monitored_folders_lock:
            monitored_folders.pop(folder_path, None)


def monitor_folder(folder_path: str):
    """
    Monitor a folder at 15-second intervals.
    After 1 minute of inactivity, send final notification and start processing progress monitoring.
    """
    logger.info(f"Starting monitoring for folder: {folder_path}")
    
    try:
        while True:
            time.sleep(CHECK_INTERVAL_SECONDS)
            
            with monitored_folders_lock:
                if folder_path not in monitored_folders:
                    logger.info(f"Folder {folder_path} removed from monitoring")
                    break
                
                folder_state = monitored_folders[folder_path]
                last_update = folder_state["last_update"]
            
            # Check for new files
            found_new = check_folder_for_new_files(folder_path)
            
            if found_new:
                logger.debug(f"New files found in {folder_path}, continuing monitoring")
                continue
            
            # Check if we've passed the inactivity timeout
            now = datetime.utcnow()
            time_since_last_update = (now - last_update).total_seconds()
            
            if time_since_last_update >= INACTIVITY_TIMEOUT_SECONDS:
                logger.info(f"No new files in {folder_path} for {INACTIVITY_TIMEOUT_SECONDS}s, preparing final notification")
                
                # Get folder statistics
                file_count, total_size = get_folder_stats(folder_path)
                
                # Idempotent final-send gate using Firestore
                try:
                    transaction = db.transaction()
                    should_send_final = check_and_mark_final(transaction, folder_path, file_count, total_size)
                except Exception as e:
                    logger.error(f"Error checking/marking final notification for {folder_path}: {e}")
                    should_send_final = False

                if should_send_final:
                    # Send final notification (edit or webhook depending on config)
                    send_final_slack_notification(folder_path, file_count, total_size)
                    # Write analytics CSV (best-effort, in background thread)
                    def write_csv_async():
                        try:
                            # Retrieve first notification time from Firestore for row
                            doc_id = folder_path.replace("/", "_").replace("\\", "_")
                            doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
                            doc = doc_ref.get()
                            data = doc.to_dict() or {}
                            first_time = data.get("first_notification_time") or ""
                            final_time_iso = datetime.utcnow().isoformat()
                            _append_completion_csv(folder_path, first_time, final_time_iso, file_count, total_size)
                        except Exception as e:
                            logger.error(f"Failed to write analytics CSV for {folder_path}: {e}")
                    
                    csv_thread = threading.Thread(target=write_csv_async, daemon=True, name=f"csv-{folder_path}")
                    csv_thread.start()
                    
                    # Start processing progress monitoring
                    with monitored_folders_lock:
                        if folder_path in monitored_folders:
                            monitored_folders[folder_path]["incoming_file_count"] = file_count
                            processing_thread = threading.Thread(
                                target=monitor_processing_progress,
                                args=(folder_path, file_count),
                                daemon=True,
                                name=f"processing-{folder_path}"
                            )
                            processing_thread.start()
                            monitored_folders[folder_path]["processing_thread"] = processing_thread
                            logger.info(f"Started processing progress monitoring for folder: {folder_path}")
                
                # Else: another instance already sent the final, skip sending
                # But we might still want to start processing monitoring if not already started
                with monitored_folders_lock:
                    if folder_path in monitored_folders and "processing_thread" not in monitored_folders[folder_path]:
                        # Another instance sent final, but we should still monitor processing
                        if "incoming_file_count" not in monitored_folders[folder_path]:
                            # Get file count from Firestore
                            doc_id = folder_path.replace("/", "_").replace("\\", "_")
                            doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
                            doc = doc_ref.get()
                            data = doc.to_dict() or {}
                            file_count = data.get("file_count", 0)
                            monitored_folders[folder_path]["incoming_file_count"] = file_count
                        
                        processing_thread = threading.Thread(
                            target=monitor_processing_progress,
                            args=(folder_path, monitored_folders[folder_path]["incoming_file_count"]),
                            daemon=True,
                            name=f"processing-{folder_path}"
                        )
                        processing_thread.start()
                        monitored_folders[folder_path]["processing_thread"] = processing_thread
                        logger.info(f"Started processing progress monitoring for folder: {folder_path} (final already sent)")
                
                # Remove from upload monitoring (but keep in dict for processing monitoring)
                with monitored_folders_lock:
                    if folder_path in monitored_folders:
                        # Keep the entry but mark upload monitoring as done
                        monitored_folders[folder_path]["upload_monitoring_done"] = True
                
                logger.info(f"Stopped upload monitoring for folder: {folder_path}, processing monitoring continues")
                break
                
    except Exception as e:
        logger.error(f"Error in monitoring thread for {folder_path}: {e}", exc_info=True)
        with monitored_folders_lock:
            monitored_folders.pop(folder_path, None)


def start_folder_monitoring(folder_path: str, initial_file: str):
    """
    Start monitoring a folder in a background thread.
    """
    with monitored_folders_lock:
        if folder_path in monitored_folders:
            # Already monitoring, just update the last update time
            monitored_folders[folder_path]["last_update"] = datetime.utcnow()
            monitored_folders[folder_path]["known_files"].add(initial_file)
            logger.debug(f"Updated monitoring for existing folder: {folder_path}")
            return
        
        # Start new monitoring
        folder_state = {
            "last_update": datetime.utcnow(),
            "known_files": {initial_file},
            "monitoring_thread": None,
        }
        monitored_folders[folder_path] = folder_state
        
        # Start monitoring thread
        thread = threading.Thread(
            target=monitor_folder,
            args=(folder_path,),
            daemon=True,
            name=f"monitor-{folder_path}"
        )
        thread.start()
        folder_state["monitoring_thread"] = thread
        
        logger.info(f"Started monitoring thread for folder: {folder_path}")


@app.route("/", methods=["POST"])
def handle_pubsub_push():
    """Handle Pub/Sub push messages."""
    try:
        envelope = request.get_json()
        if not envelope:
            logger.warning("No Pub/Sub message received")
            return "Bad Request: no Pub/Sub message received", 400

        if not isinstance(envelope, dict) or "message" not in envelope:
            logger.warning("Invalid Pub/Sub message format")
            return "Bad Request: invalid Pub/Sub message format", 400

        pubsub_message = envelope["message"]

        # Decode the message data
        if "data" in pubsub_message:
            message_data = base64.b64decode(pubsub_message["data"]).decode("utf-8")
            logger.info(f"Received message: {message_data}")

            try:
                data = json.loads(message_data)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse message data as JSON: {message_data}")
                return "OK", 200  # Still return OK to acknowledge the message

            # Extract file information from GCS notification
            file_name = data.get("name", "")
            bucket = data.get("bucket", "")
            event_time = data.get("timeCreated", datetime.utcnow().isoformat())

            logger.info(f"Processing file: {bucket}/{file_name}")

            # Check if this is in a monitored path
            is_monitored = is_monitored_path(file_name)
            logger.debug(f"Bucket match: {bucket == BUCKET_NAME}, Is monitored: {is_monitored}, MONITORED_PREFIXES: {MONITORED_PREFIXES}")
            
            if bucket == BUCKET_NAME and is_monitored:
                folder_path = get_folder_from_path(file_name)
                logger.debug(f"Extracted folder_path: '{folder_path}' from file: {file_name}")

                if folder_path:
                    # Atomically check and mark folder (prevents race conditions)
                    transaction = db.transaction()
                    should_notify = check_and_mark_folder(transaction, folder_path, event_time)

                    if should_notify:
                        logger.info(f"New folder detected: {folder_path}")
                        # Send Slack notification in background to avoid blocking request
                        def send_notification_async():
                            try:
                                if send_slack_notification(folder_path, event_time):
                                    logger.info(f"Notification sent for folder: {folder_path}")
                                else:
                                    logger.warning(f"Failed to send Slack notification for folder: {folder_path}")
                            except Exception as e:
                                logger.error(f"Error sending Slack notification for {folder_path}: {e}")
                        
                        notification_thread = threading.Thread(target=send_notification_async, daemon=True, name=f"notify-{folder_path}")
                        notification_thread.start()
                        
                        # Start monitoring this folder (non-blocking)
                        start_folder_monitoring(folder_path, file_name)
                    else:
                        logger.debug(f"Folder already notified: {folder_path}")
                        # Even if already notified, we might want to track this file for monitoring
                        # Check if we're still monitoring this folder (fast in-memory check)
                        with monitored_folders_lock:
                            if folder_path in monitored_folders:
                                # Update monitoring with this new file
                                monitored_folders[folder_path]["last_update"] = datetime.utcnow()
                                monitored_folders[folder_path]["known_files"].add(file_name)
                            else:
                                # Folder was already notified but monitoring completed or never started
                                # Check Firestore asynchronously to avoid blocking request
                                def check_and_start_monitoring_async():
                                    try:
                                        doc_id = folder_path.replace("/", "_").replace("\\", "_")
                                        doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
                                        doc = doc_ref.get()
                                        data = doc.to_dict() or {}
                                        if doc.exists and not data.get("final_notification_sent"):
                                            # Final notification not sent yet, start monitoring
                                            start_folder_monitoring(folder_path, file_name)
                                    except Exception as e:
                                        logger.error(f"Error checking Firestore for monitoring {folder_path}: {e}")
                                
                                check_thread = threading.Thread(target=check_and_start_monitoring_async, daemon=True, name=f"check-{folder_path}")
                                check_thread.start()
                else:
                    logger.debug(f"Empty folder path for file: {file_name}")
            else:
                logger.debug(f"File not in monitored path: {file_name}")

        return "OK", 200

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        return "Internal Server Error", 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"}), 200


@app.route("/_ah/warmup", methods=["GET"])
def warmup():
    """Warmup endpoint for Cloud Run."""
    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)

