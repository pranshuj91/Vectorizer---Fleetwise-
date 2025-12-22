from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


def build_sections(blocks: List[Dict[str, str]]) -> List[Dict[str, List[str]]]:
    """
    Group reconstructed blocks into sections.

    Input blocks are expected to have:
      { "type": "heading" | "paragraph", "text": "..." }

    Output format:
    [
      {
        "section_title": "Title",
        "content": ["Paragraph 1...", "Paragraph 2..."]
      },
      ...
    ]
    """
    sections: List[Dict[str, List[str]]] = []

    current_title = "Introduction"
    current_paragraphs: List[str] = []

    def flush_section() -> None:
        nonlocal current_title, current_paragraphs
        if current_paragraphs:
            sections.append(
                {
                    "section_title": current_title,
                    "content": current_paragraphs,
                }
            )
            current_paragraphs = []

    for block in blocks:
        b_type = block.get("type")
        text = (block.get("text") or "").strip()
        if not text:
            continue

        if b_type == "heading":
            # Close previous section if it had content
            flush_section()
            current_title = text
        else:
            current_paragraphs.append(text)

    # Flush trailing section
    flush_section()

    # If no sections at all (e.g., empty doc), return empty list
    return sections


def save_sections(sections: List[Dict[str, List[str]]], output_path: Path) -> None:
    """
    Save sectioned structure as JSON to disk.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(sections, f, ensure_ascii=False, indent=2)


