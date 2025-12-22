from __future__ import annotations

from pathlib import Path
from typing import Iterable, List
import json


def _yield_tokens_from_file(text_file_path: Path) -> Iterable[str]:
    """
    Lazily yield whitespace-separated tokens from a text file.
    """
    with text_file_path.open("r", encoding="utf-8") as f:
        for line in f:
            # Split on whitespace to approximate tokens
            for token in line.strip().split():
                if token:
                    yield token


def chunk_text_file(
    text_file_path: Path,
    target_chunk_size_tokens: int = 600,
    overlap_tokens: int = 50,
    jsonl_output_path: Path | None = None,
) -> List[str]:
    """
    Chunk a large text file into overlapping text chunks using approximate tokens.

    Tokens are approximated by splitting on whitespace. Each chunk will contain
    roughly `target_chunk_size_tokens` tokens, with `overlap_tokens` tokens of
    overlap between consecutive chunks to preserve context.

    :param text_file_path: Path to the input .txt file.
    :param target_chunk_size_tokens: Desired number of tokens per chunk.
    :param overlap_tokens: Number of tokens to overlap between chunks.
    :param jsonl_output_path: Optional path to a JSONL file where chunks will be
        written in a streaming-friendly format. Each line will be a JSON object:
        {"chunk_id": int, "text": str, "page_start": null, "page_end": null}.
    :return: List of text chunks.
    """
    if target_chunk_size_tokens <= 0:
        raise ValueError("target_chunk_size_tokens must be positive.")
    if overlap_tokens < 0:
        raise ValueError("overlap_tokens cannot be negative.")
    if overlap_tokens >= target_chunk_size_tokens:
        raise ValueError("overlap_tokens must be smaller than target_chunk_size_tokens.")

    chunks: List[str] = []
    current_tokens: List[str] = []

    for token in _yield_tokens_from_file(text_file_path):
        current_tokens.append(token)
        if len(current_tokens) >= target_chunk_size_tokens:
            # Finalize current chunk
            chunks.append(" ".join(current_tokens))
            # Prepare next chunk with overlap
            if overlap_tokens > 0:
                current_tokens = current_tokens[-overlap_tokens:]
            else:
                current_tokens = []

    # Add remaining tokens as a final chunk
    if current_tokens:
        chunks.append(" ".join(current_tokens))

    # Optionally persist chunks to JSONL on disk for later inspection/download.
    # Page information is currently not tracked at the chunking level, so
    # page_start and page_end are set to null (JSON null).
    if jsonl_output_path is not None:
        jsonl_output_path.parent.mkdir(parents=True, exist_ok=True)
        with jsonl_output_path.open("w", encoding="utf-8") as f:
            for chunk_id, text in enumerate(chunks):
                record = {
                    "chunk_id": chunk_id,
                    "text": text,
                    "page_start": None,
                    "page_end": None,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return chunks


