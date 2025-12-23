from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List


def _flatten_json(obj: Any, parent_key: str = "") -> Dict[str, Any]:
    """
    Flatten a nested JSON-like structure into a flat dictionary using dot-notation.

    Lists are indexed numerically: parent.0.child, parent.1.child, etc.
    """
    items: Dict[str, Any] = {}

    if isinstance(obj, dict):
        for key, value in obj.items():
            new_key = f"{parent_key}.{key}" if parent_key else str(key)
            items.update(_flatten_json(value, new_key))
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            new_key = f"{parent_key}.{idx}" if parent_key else str(idx)
            items.update(_flatten_json(value, new_key))
    else:
        items[parent_key] = obj

    return items


def extract_json_blocks(
    raw_bytes: bytes,
    file_name: str,
) -> List[Dict[str, Any]]:
    """
    Parse a JSON payload and convert it into semantic text blocks suitable for RAG.

    The entire JSON document is flattened using dot-notation, and all key-value
    pairs are rendered as "path: value" lines in a single semantic block.
    """
    try:
        data = json.loads(raw_bytes.decode("utf-8", errors="ignore"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON content.") from exc

    flat = _flatten_json(data)

    lines: List[str] = []
    for key, value in flat.items():
        # Render complex values as JSON to keep them readable
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value, ensure_ascii=False)
        else:
            value_str = str(value)
        lines.append(f"{key}: {value_str}")

    text_block = "\n".join(lines)

    return [
        {
            "source_file": file_name,
            "source_type": "json",
            "block_id": 0,
            "text": text_block,
        }
    ]


