from __future__ import annotations

import logging
from typing import Any, Dict, List

from .embedding_providers import get_provider_from_env
from .vector_store_supabase import upsert_embeddings


def ingest_chunks_to_supabase(chunks: List[Dict[str, Any]], file_id: str, file_name: str) -> None:
    """
    Ingest semantic chunks into Supabase pgvector using a configured provider.

    - Provider is selected via EMBEDDING_PROVIDER env var.
    - If configuration is missing or invalid, an explicit error is logged.
    - Supabase / provider errors do NOT crash the main request flow.
    """
    if not chunks:
        return

    try:
        provider = get_provider_from_env()
    except Exception as exc:  # pragma: no cover - defensive
        logging.error("Embedding provider configuration error: %s", exc)
        return

    records: List[Dict[str, Any]] = []

    for chunk in chunks:
        text = str(chunk.get("text", "")).strip()
        if not text:
            continue

        try:
            embedding = provider.embed(text)
        except Exception as exc:  # pragma: no cover - defensive
            logging.warning("Embedding generation failed for chunk %s: %s", chunk.get("chunk_id"), exc)
            continue

        records.append(
            {
                "file_id": file_id,
                "chunk_id": int(chunk.get("chunk_id", 0)),
                "section": chunk.get("section", "Untitled"),
                "content": text,
                "embedding": embedding,
            }
        )

    if not records:
        logging.info("No embeddings generated; skipping Supabase upsert.")
        return

    try:
        upsert_embeddings(records)
        logging.info("Ingested %d embeddings to Supabase for file_id=%s", len(records), file_id)
    except RuntimeError as exc:
        # RuntimeError indicates configuration issues (missing env vars, client creation failure)
        # These should have been caught at startup, but re-raise to fail fast
        logging.error("Supabase configuration error: %s", exc)
        raise
    except Exception as exc:
        # Other exceptions (network, API errors) are logged but don't crash the upload flow
        logging.error("Failed to upsert embeddings into Supabase: %s", exc)
        # Do NOT log success if upsert failed


