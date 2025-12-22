from __future__ import annotations

import json
import re
from typing import Dict, List


def _normalize_newlines(text: str) -> str:
    """
    Normalize different newline styles to simple '\n'.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _split_paragraph_blocks(text: str) -> List[str]:
    """
    Split text into paragraph-like blocks using double newlines.

    Single newlines are considered soft wraps and are handled later.
    """
    # Use regex to treat 2+ newlines as a boundary
    blocks = re.split(r"\n\s*\n", text)
    return [b.strip() for b in blocks if b.strip()]


def _merge_soft_lines(block: str) -> str:
    """
    Merge lines within a paragraph block, repairing line-wrapped sentences.

    Rules:
    - If a line does NOT end with [. ? ! : ;] and the next line starts with a
      lowercase letter, merge them with a single space.
    - All remaining single newlines are converted to spaces.
    """
    lines = block.split("\n")
    merged: List[str] = []
    idx = 0

    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            idx += 1
            continue

        # Attempt to merge with subsequent lines according to the rule
        while idx + 1 < len(lines):
            next_line_raw = lines[idx + 1]
            next_line = next_line_raw.lstrip()
            if not next_line:
                break

            last_char = line[-1] if line else ""
            first_char_next = next_line[0]
            if last_char not in ".?!:;" and first_char_next.islower():
                # Merge soft-wrapped sentence continuation
                line = f"{line} {next_line}"
                idx += 1
            else:
                break

        merged.append(line)
        idx += 1

    # Any remaining line breaks inside the block are soft wraps -> spaces
    paragraph_text = " ".join(merged)
    # Collapse excess whitespace
    paragraph_text = re.sub(r"\s+", " ", paragraph_text).strip()
    return paragraph_text


def _is_all_caps(text: str) -> bool:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    return all(ch.isupper() for ch in letters)


def _is_title_case(text: str) -> bool:
    words = [w for w in re.split(r"\s+", text) if w]
    if not words:
        return False
    ok_words = 0
    for w in words:
        if len(w) == 1:
            if w[0].isupper():
                ok_words += 1
        else:
            if w[0].isupper() and w[1:].islower():
                ok_words += 1
    return ok_words == len(words)


def _looks_like_heading(text: str) -> bool:
    """
    Heuristic heading detector based on text shape only.
    """
    text = text.strip()
    if not text:
        return False
    if len(text) >= 70:
        return False
    if text[-1] in ".?!:;":
        return False

    return _is_all_caps(text) or _is_title_case(text)


def reconstruct_document(raw_text: str) -> List[Dict[str, str]]:
    """
    Backwards-compatible helper used elsewhere. Prefer reconstruct_text
    for new code paths.
    """
    normalized = _normalize_newlines(raw_text)
    blocks = _split_paragraph_blocks(normalized)

    reconstructed: List[Dict[str, str]] = []

    for idx, block in enumerate(blocks):
        paragraph_text = _merge_soft_lines(block)
        if not paragraph_text:
            continue

        is_heading_candidate = _looks_like_heading(paragraph_text)
        next_block_exists = idx + 1 < len(blocks)
        prev_block_exists = idx > 0

        # Approximate "surrounded by blank lines" by requiring that this block
        # is neither the first nor the last logical block.
        if is_heading_candidate and next_block_exists and prev_block_exists:
            reconstructed.append({"type": "heading", "text": paragraph_text})
        else:
            reconstructed.append({"type": "paragraph", "text": paragraph_text})

    return reconstructed


def reconstruct_text(raw_text: str) -> List[Dict[str, List[str]]]:
    """
    High-level semantic repair entrypoint.

    Applies line merging, paragraph detection, and heading detection, and
    returns a list of sections:

    [
      { "title": "Section Title", "paragraphs": ["Paragraph text...", ...] },
      ...
    ]

    If content appears before the first heading, it is grouped under the
    title "Introduction".
    """
    normalized = _normalize_newlines(raw_text)
    blocks = _split_paragraph_blocks(normalized)

    # First classify blocks as headings or paragraphs
    typed_blocks: List[Dict[str, str]] = []
    for idx, block in enumerate(blocks):
        paragraph_text = _merge_soft_lines(block)
        if not paragraph_text:
            continue

        is_heading_candidate = _looks_like_heading(paragraph_text)
        next_block_exists = idx + 1 < len(blocks)
        prev_block_exists = idx > 0

        if is_heading_candidate and next_block_exists and prev_block_exists:
            typed_blocks.append({"type": "heading", "text": paragraph_text})
        else:
            typed_blocks.append({"type": "paragraph", "text": paragraph_text})

    # Then group into sections
    sections: List[Dict[str, List[str]]] = []
    current_title = "Introduction"
    current_paragraphs: List[str] = []

    def flush_section() -> None:
        nonlocal current_title, current_paragraphs
        if current_paragraphs:
            sections.append(
                {
                    "title": current_title,
                    "paragraphs": current_paragraphs,
                }
            )
            current_paragraphs = []

    for block in typed_blocks:
        b_type = block.get("type")
        text = (block.get("text") or "").strip()
        if not text:
            continue

        if b_type == "heading":
            flush_section()
            current_title = text
        else:
            current_paragraphs.append(text)

    flush_section()

    return sections


def save_reconstructed_document(blocks: List[Dict[str, str]], output_path: str) -> None:
    """
    Save reconstructed blocks as JSON to disk.
    """
    from pathlib import Path

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(blocks, f, ensure_ascii=False, indent=2)


