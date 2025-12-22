from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF


@dataclass
class Paragraph:
    text: str
    page: int


@dataclass
class Section:
    type: str
    title: str
    page_start: int
    page_end: int
    paragraphs: List[Paragraph]


def _compute_body_font_size(doc: fitz.Document) -> float:
    """
    Compute an approximate body font size by taking the median of all span sizes.
    """
    sizes: List[float] = []
    for page in doc:
        page_dict = page.get_text("dict")
        for block in page_dict.get("blocks", []):
            if block.get("type", 0) != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size = span.get("size")
                    if isinstance(size, (int, float)):
                        sizes.append(float(size))
    if not sizes:
        return 10.0
    return float(median(sizes))


def _is_heading(block_spans: List[Dict[str, Any]], body_font_size: float) -> bool:
    """
    Heuristic to decide if a text block is a section heading.

    Criteria:
    - Maximum font size significantly larger than body font size.
    - At least one span appears bold by font name or flags.
    """
    if not block_spans:
        return False

    max_size = max(float(span.get("size", 0.0)) for span in block_spans)
    if max_size < body_font_size * 1.1:
        return False

    for span in block_spans:
        font_name = (span.get("font") or "").lower()
        flags = int(span.get("flags", 0))
        is_bold = "bold" in font_name or (flags & 2) != 0
        if is_bold:
            return True

    return False


def parse_pdf_to_structured(pdf_path: Path) -> List[Section]:
    """
    Parse a PDF into an ordered list of sections using layout-aware extraction.

    Each section contains a title, page range, and ordered paragraphs.
    """
    doc = fitz.open(pdf_path)
    body_font_size = _compute_body_font_size(doc)

    sections: List[Section] = []
    current_section: Optional[Section] = None

    for page_index in range(doc.page_count):
        page = doc.load_page(page_index)
        page_number = page_index + 1
        page_dict = page.get_text("dict")

        for block in page_dict.get("blocks", []):
            if block.get("type", 0) != 0:
                continue

            spans: List[Dict[str, Any]] = []
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    spans.append(span)

            if not spans:
                continue

            text = "".join(span.get("text", "") for span in spans).strip()
            if not text:
                continue

            is_heading = _is_heading(spans, body_font_size)

            if is_heading:
                # Close previous section if it had any content
                if current_section is not None:
                    sections.append(current_section)

                current_section = Section(
                    type="section",
                    title=text,
                    page_start=page_number,
                    page_end=page_number,
                    paragraphs=[],
                )
            else:
                # Regular paragraph
                if current_section is None:
                    # Create a default catch-all section if the document starts
                    # with body text before any clear heading.
                    current_section = Section(
                        type="section",
                        title="Untitled",
                        page_start=page_number,
                        page_end=page_number,
                        paragraphs=[],
                    )

                current_section.paragraphs.append(Paragraph(text=text, page=page_number))
                # Extend section page range as needed
                if page_number < current_section.page_start:
                    current_section.page_start = page_number
                if page_number > current_section.page_end:
                    current_section.page_end = page_number

    if current_section is not None:
        sections.append(current_section)

    doc.close()
    return sections


def save_structured_document(sections: List[Section], output_path: Path) -> None:
    """
    Serialize structured sections to JSON on disk.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert dataclasses to simple dicts, and nested Paragraphs likewise.
    serializable: List[Dict[str, Any]] = []
    for section in sections:
        section_dict = asdict(section)
        # Rename 'paragraphs' entries to ensure JSON-friendly structure
        section_dict["paragraphs"] = [
            {"text": p["text"], "page": p["page"]}
            for p in section_dict.get("paragraphs", [])
        ]
        serializable.append(section_dict)

    import json

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


