from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from .vector_store_supabase import _get_supabase_client


def is_already_processed(drive_file_id: str) -> bool:
    """
    Check if a Google Drive file has already been processed.

    Returns True if the file exists in the processed_files table.
    """
    try:
        client = _get_supabase_client()
        response = (
            client.table("processed_files")
            .select("drive_file_id")
            .eq("drive_file_id", drive_file_id)
            .limit(1)
            .execute()
        )
        return len(response.data) > 0
    except Exception as exc:
        logging.error("Failed to check processed_files table: %s", exc)
        raise


def mark_as_processed(drive_file_id: str, file_name: str, folder_path: str) -> None:
    """
    Mark a Google Drive file as processed in the processed_files table.

    This should be called ONLY after successful embedding and storage.
    """
    try:
        client = _get_supabase_client()
        row = {
            "drive_file_id": drive_file_id,
            "file_name": file_name,
            "folder_path": folder_path,
            "processed_at": datetime.utcnow().isoformat(),
        }
        client.table("processed_files").upsert(row).execute()
        logging.info("Marked drive_file_id=%s as processed", drive_file_id)
    except Exception as exc:
        logging.error("Failed to mark file as processed: %s", exc)
        raise

