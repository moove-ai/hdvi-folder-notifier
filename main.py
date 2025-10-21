import base64
import json
import os
import logging
from datetime import datetime
from typing import Dict, Set
from flask import Flask, request, jsonify
import requests
from google.cloud import firestore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT", "moove-data-pipelines")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "moove-incoming-data-u7x4ty")
MONITORED_PREFIXES = os.environ.get("MONITORED_PREFIXES", "Prebind/,Postbind/,test/").split(",")

# Initialize Firestore to track notified folders
db = firestore.Client(project=PROJECT_ID)
COLLECTION_NAME = "notified_folders"


def get_folder_from_path(file_path: str) -> str:
    """
    Extract the top-level monitored folder from a file path.
    Example: Prebind/2024/10/20/file.csv -> Prebind
    """
    # Find which monitored prefix this file belongs to
    for prefix in MONITORED_PREFIXES:
        if file_path.startswith(prefix):
            return prefix
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
        },
    )
    return True  # New folder, should notify


def send_slack_notification(folder_path: str, timestamp: str) -> bool:
    """Send notification to Slack."""
    if not SLACK_WEBHOOK_URL:
        logger.warning("SLACK_WEBHOOK_URL not configured, skipping notification")
        return False

    message = {
        "text": f"🆕 New folder detected in HDVI data",
        "blocks": [
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
        ],
    }

    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=message, timeout=10)
        response.raise_for_status()
        logger.info(f"Slack notification sent for folder: {folder_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")
        return False


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
            if bucket == BUCKET_NAME and is_monitored_path(file_name):
                folder_path = get_folder_from_path(file_name)

                if folder_path:
                    # Atomically check and mark folder (prevents race conditions)
                    transaction = db.transaction()
                    should_notify = check_and_mark_folder(transaction, folder_path, event_time)

                    if should_notify:
                        logger.info(f"New folder detected: {folder_path}")
                        # Send Slack notification
                        if send_slack_notification(folder_path, event_time):
                            logger.info(f"Notification sent for folder: {folder_path}")
                        else:
                            logger.warning(f"Failed to send Slack notification for folder: {folder_path}")
                            # Note: Folder is still marked as notified in Firestore to prevent retries
                    else:
                        logger.debug(f"Folder already notified: {folder_path}")
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

