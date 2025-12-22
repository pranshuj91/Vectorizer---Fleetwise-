from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def _count_tokens(text: str) -> int:
    """
    Approximate token count using whitespace splitting.
    """
    return len(text.split())


def build_semantic_chunks(
    sections: List[Dict[str, Any]],
    target_tokens: int = 400,
    overlap_ratio: float = 0.15,
) -> List[Dict[str, Any]]:
    """
    Build semantic chunks from sectioned paragraphs.

    Rules:
    - Chunk ONLY at paragraph boundaries.
    - Never split sentences (paragraphs are treated as atomic units).
    - Chunks can span multiple paragraphs but stay within the same section.
    - Target chunk size is ~target_tokens with ~overlap_ratio overlap.

    Input sections format:
    [
      {
        "section_title": "Title",
        "content": ["Paragraph 1...", "Paragraph 2..."]
      },
      ...
    ]

    Output chunk format:
    {
      "chunk_id": int,
      "section": str,
      "text": str,
    }
    """
    if target_tokens <= 0:
        raise ValueError("target_tokens must be positive.")
    if not (0.0 <= overlap_ratio < 1.0):
        raise ValueError("overlap_ratio must be in [0, 1).")

    chunks: List[Dict[str, Any]] = []
    chunk_id = 0
    overlap_tokens_target = int(target_tokens * overlap_ratio)

    for section in sections:
        title = section.get("section_title") or "Untitled"
        paragraphs: List[str] = section.get("content", [])

        current_paragraphs: List[str] = []
        current_tokens = 0

        def flush_chunk() -> None:
            nonlocal chunk_id, current_paragraphs, current_tokens
            if not current_paragraphs:
                return
            text = "\n\n".join(current_paragraphs).strip()
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "section": title,
                    "text": text,
                }
            )
            chunk_id += 1

            if overlap_tokens_target > 0:
                # Retain trailing paragraphs until we reach the overlap budget
                retained: List[str] = []
                token_acc = 0
                for para in reversed(current_paragraphs):
                    token_acc += _count_tokens(para)
                    retained.append(para)
                    if token_acc >= overlap_tokens_target:
                        break
                retained.reverse()
                current_paragraphs = retained
                current_tokens = sum(_count_tokens(p) for p in current_paragraphs)
            else:
                current_paragraphs = []
                current_tokens = 0

        for para in paragraphs:
            para = (para or "").strip()
            if not para:
                continue

            para_tokens = _count_tokens(para)
            if current_tokens + para_tokens > target_tokens and current_paragraphs:
                flush_chunk()

            current_paragraphs.append(para)
            current_tokens += para_tokens

        flush_chunk()

    return chunks


def save_chunks_jsonl(chunks: List[Dict[str, Any]], jsonl_path: Path) -> None:
    """
    Save semantic chunks to disk as JSONL.
    """
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
