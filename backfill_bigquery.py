#!/usr/bin/env python3
"""
Manual BigQuery backfill for hdvi-folder-notifier completion metrics.

Usage examples:
  python backfill_bigquery.py --start-date 2025-11-09
  python backfill_bigquery.py --start-date 2025-11-09T00:00:00Z --end-date 2025-11-15T00:00:00Z --limit 100

Environment fallbacks:
  BACKFILL_START_DATE / BACKFILL_END_DATE (ISO-8601)
  DISABLE_COMPLETION_THREAD is forced to true to avoid spawning monitor threads.
"""

import argparse
import os
from datetime import datetime, timezone
from typing import Optional

# Ensure we don't start the periodic completion thread when importing main.
os.environ.setdefault("DISABLE_COMPLETION_THREAD", "true")

import main  # noqa: E402  pylint: disable=wrong-import-position


logger = main.logger


def _parse_target_timestamp(value: Optional[str], label: str) -> Optional[datetime]:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    # Allow YYYY-MM-DD shorthand.
    if len(text) == 10 and text.count("-") == 2:
        text = f"{text}T00:00:00Z"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError as exc:
        raise SystemExit(f"Invalid {label}: {value}") from exc


def _to_iso_string(value) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    return str(value)


def _should_backfill(data: dict, first_dt: Optional[datetime], start_dt: datetime, end_dt: Optional[datetime]) -> bool:
    if not data.get("final_notification_sent"):
        return False
    if not first_dt:
        return False
    if first_dt < start_dt:
        return False
    if end_dt and first_dt >= end_dt:
        return False
    return True


def _backfill_row(doc_id: str, data: dict, dry_run: bool = False) -> bool:
    folder_path = data.get("folder_path") or doc_id.replace("_", "/")
    first_time_raw = data.get("first_notification_time")
    final_time_raw = data.get("final_notification_time")
    final_time_iso = _to_iso_string(final_time_raw)
    if not folder_path or not final_time_iso or not first_time_raw:
        logger.debug("Skipping %s due to missing folder or timestamps", doc_id)
        return False

    file_count = int(data.get("file_count") or 0)
    total_size = int(data.get("total_size_bytes") or 0)
    if file_count <= 0:
        logger.debug("Skipping %s due to empty file_count", folder_path)
        return False

    generation = data.get("generation", 1)
    reactivation_count = data.get("reactivation_count", 0)

    duration_seconds = main._duration_seconds(first_time_raw, final_time_iso)
    duration_display = main.format_time_difference(
        main.round_timestamp_to_second(first_time_raw),
        main.round_timestamp_to_second(final_time_iso),
    )
    time_per_gb_display, time_per_gb_seconds = main._compute_time_per_gb(duration_seconds, total_size)

    if dry_run:
        logger.info(
            "[DRY RUN] Would backfill %s (generation=%s, first=%s, final=%s, files=%s, size=%s)",
            folder_path,
            generation,
            first_time_raw,
            final_time_iso,
            file_count,
            total_size,
        )
        return True

    main._write_bigquery_folder_completion(
        folder_path=folder_path,
        generation=generation,
        reactivation_count=reactivation_count,
        first_time=_to_iso_string(first_time_raw),
        final_time_iso=final_time_iso,
        file_count=file_count,
        total_size=total_size,
        duration_seconds=duration_seconds,
        duration_display=duration_display,
        time_per_gb_seconds=time_per_gb_seconds,
        time_per_gb_display=time_per_gb_display,
    )

    logger.info(
        "Backfilled %s (generation=%s, files=%s, size=%s bytes)",
        folder_path,
        generation,
        file_count,
        total_size,
    )
    return True


def run_backfill(start_dt: datetime, end_dt: Optional[datetime], limit: Optional[int], dry_run: bool) -> None:
    collection = main.db.collection(main.COLLECTION_NAME)
    docs = collection.stream()
    processed = 0
    eligible = 0
    inserted = 0
    skipped = 0

    for doc in docs:
        processed += 1
        data = doc.to_dict() or {}
        first_dt = main._parse_iso_timestamp(data.get("first_notification_time"))
        if not _should_backfill(data, first_dt, start_dt, end_dt):
            skipped += 1
            continue

        eligible += 1
        if limit and inserted >= limit:
            break

        success = _backfill_row(doc.id, data, dry_run=dry_run)
        if success:
            inserted += 1

    logger.info(
        "Backfill complete: processed=%s eligible=%s inserted=%s skipped=%s dry_run=%s",
        processed,
        eligible,
        inserted,
        skipped,
        dry_run,
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Backfill folder completion stats into BigQuery.")
    parser.add_argument("--start-date", help="ISO-8601 start timestamp (UTC). Required if env BACKFILL_START_DATE not set.")
    parser.add_argument("--end-date", help="Optional ISO-8601 end timestamp (exclusive).")
    parser.add_argument("--limit", type=int, help="Maximum number of rows to insert.")
    parser.add_argument("--dry-run", action="store_true", help="Plan mode; log rows without inserting.")
    return parser.parse_args()


def main_cli():
    args = parse_args()
    start_source = args.start_date or os.environ.get("BACKFILL_START_DATE")
    if not start_source:
        raise SystemExit("Missing start date. Provide --start-date or BACKFILL_START_DATE.")
    start_dt = _parse_target_timestamp(start_source, "start date")
    end_dt = _parse_target_timestamp(args.end_date or os.environ.get("BACKFILL_END_DATE"), "end date")
    if not start_dt:
        raise SystemExit("Unable to parse start date.")
    logger.info(
        "Starting BigQuery backfill from %s%s",
        start_dt.isoformat(),
        f" to {end_dt.isoformat()}" if end_dt else "",
    )
    run_backfill(start_dt, end_dt, args.limit, args.dry_run)


if __name__ == "__main__":
    main_cli()

