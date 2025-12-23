from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Tuple

import psycopg2


def _get_connection():
    """
    Create a new psycopg2 connection using SUPABASE_DB_URL.

    If the env var is missing, return None so callers can no-op gracefully.
    """
    dsn = os.getenv("SUPABASE_DB_URL")
    if not dsn:
        return None
    return psycopg2.connect(dsn)


def _embedding_to_vector_literal(embedding: List[float]) -> str:
    """
    Convert a list[float] into a pgvector-compatible text literal.

    Example: [0.1, 0.2] -> '[0.1,0.2]'
    """
    return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"


def upsert_embeddings(records: Iterable[Dict[str, Any]]) -> None:
    """
    Insert embeddings into a Supabase Postgres table with pgvector.

    Expects a table with schema like:
      CREATE TABLE IF NOT EXISTS document_embeddings (
        id bigserial primary key,
        file_id text,
        chunk_id int,
        section text,
        content text,
        embedding vector
      );

    Connection errors or configuration issues are swallowed so that the
    main application flow continues even when Supabase is not configured.
    """
    conn = _get_connection()
    if conn is None:
        return

    rows: List[Tuple[Any, ...]] = []
    for rec in records:
        embedding = rec.get("embedding")
        if not embedding:
            continue
        rows.append(
            (
                rec.get("file_id"),
                rec.get("chunk_id"),
                rec.get("section"),
                rec.get("content"),
                _embedding_to_vector_literal(embedding),
            )
        )

    if not rows:
        conn.close()
        return

    sql = """
    INSERT INTO document_embeddings (file_id, chunk_id, section, content, embedding)
    VALUES (%s, %s, %s, %s, %s::vector)
    """

    try:
        with conn:
            with conn.cursor() as cur:
                cur.executemany(sql, rows)
    finally:
        conn.close()


