from __future__ import annotations

import csv
from io import StringIO
from typing import Any, Dict, List


def extract_csv_blocks(
    raw_bytes: bytes,
    file_name: str,
    encoding: str = "utf-8",
) -> List[Dict[str, Any]]:
    """
    Convert a CSV file into semantic text blocks.

    Each row becomes one block, including:
    - row number (1-based, including header row)
    - column names
    - cell values
    """
    text = raw_bytes.decode(encoding, errors="ignore")
    reader = csv.reader(StringIO(text))

    rows = list(reader)
    if not rows:
        return []

    header = rows[0]
    blocks: List[Dict[str, Any]] = []

    block_id = 0
    for row_index, row in enumerate(rows[1:], start=2):  # 1-based with header row as 1
        if not any(cell.strip() for cell in row):
            continue

        lines = [f"Row {row_index} of {file_name}"]
        for col_name, value in zip(header, row):
            col_name = (col_name or "").strip() or "column"
            value = (value or "").strip()
            lines.append(f"{col_name}: {value}")

        text_block = "\n".join(lines)
        blocks.append(
            {
                "source_file": file_name,
                "source_type": "csv",
                "block_id": block_id,
                "text": text_block,
            }
        )
        block_id += 1

    return blocks


