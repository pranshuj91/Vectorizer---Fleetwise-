from __future__ import annotations

import logging
import os
from typing import Any, Dict, Iterable

from supabase import create_client, Client


def _get_supabase_client() -> Client:
    """
    Create a Supabase REST API client using SUPABASE_URL and SUPABASE_SERVICE_KEY.

    Raises RuntimeError if env vars are missing or client creation fails.
    This ensures fail-fast behavior instead of silent skipping.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_url.strip():
        raise RuntimeError("SUPABASE_URL is missing or empty. Cannot create Supabase client.")

    if not supabase_key or not supabase_key.strip():
        raise RuntimeError("SUPABASE_SERVICE_KEY is missing or empty. Cannot create Supabase client.")

    try:
        return create_client(supabase_url.strip(), supabase_key.strip())
    except Exception as exc:
        raise RuntimeError(f"Failed to create Supabase client: {exc}") from exc


def upsert_embeddings(records: Iterable[Dict[str, Any]]) -> None:
    """
    Insert embeddings into a Supabase table via REST API.

    Expects a table named 'document_embeddings' with schema:
      - id: bigserial primary key (auto-generated)
      - file_id: text
      - chunk_id: integer
      - section: text
      - content: text
      - embedding: vector (pgvector type)

    Note: Supabase REST API handles pgvector types automatically when
    inserting JSON arrays. The embedding should be a list[float].

    Raises RuntimeError if Supabase client cannot be created or if upsert fails.
    This ensures fail-fast behavior instead of silent skipping.
    """
    client = _get_supabase_client()  # Raises RuntimeError if env vars missing

    rows = []
    for rec in records:
        embedding = rec.get("embedding")
        if not embedding or not isinstance(embedding, list):
            continue

        rows.append(
            {
                "file_id": rec.get("file_id"),
                "chunk_id": rec.get("chunk_id"),
                "section": rec.get("section"),
                "content": rec.get("content"),
                "embedding": embedding,  # Supabase REST API accepts list[float] directly
            }
        )

    if not rows:
        logging.info("No embedding records to upsert.")
        return

    # Use upsert to handle duplicates (match on file_id + chunk_id if you have a unique constraint)
    response = client.table("document_embeddings").upsert(rows).execute()
    logging.info("Upserted %d embeddings to Supabase table 'document_embeddings'", len(rows))

