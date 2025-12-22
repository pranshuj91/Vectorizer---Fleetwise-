from __future__ import annotations

from pathlib import Path
from typing import BinaryIO
import uuid

import fitz  # PyMuPDF
from fastapi import UploadFile


def _generate_unique_filename(original_name: str) -> str:
    """
    Generate a unique filename preserving the original extension.
    """
    suffix = Path(original_name).suffix
    stem = Path(original_name).stem
    unique_id = uuid.uuid4().hex[:8]
    return f"{stem}_{unique_id}{suffix}"


async def save_upload_file(
    upload_file: UploadFile,
    upload_dir: Path,
    max_size_bytes: int,
) -> Path:
    """
    Save an uploaded file to disk while enforcing a maximum size.

    The file is streamed in chunks to avoid loading it entirely into memory.

    :param upload_file: The FastAPI UploadFile instance.
    :param upload_dir: Directory to save the file into.
    :param max_size_bytes: Maximum allowed file size in bytes.
    :return: Path to the saved file.
    :raises ValueError: If the file exceeds the maximum allowed size.
    """
    upload_dir.mkdir(parents=True, exist_ok=True)

    unique_name = _generate_unique_filename(upload_file.filename or "uploaded.pdf")
    destination = upload_dir / unique_name

    bytes_written = 0
    chunk_size = 1024 * 1024  # 1MB

    with destination.open("wb") as out_file:
        while True:
            chunk = await upload_file.read(chunk_size)
            if not chunk:
                break
            bytes_written += len(chunk)
            if bytes_written > max_size_bytes:
                destination.unlink(missing_ok=True)
                raise ValueError("File exceeds maximum allowed size.")
            out_file.write(chunk)

    await upload_file.close()
    return destination


def extract_text_from_pdf(pdf_path: Path, text_output_path: Path) -> int:
    """
    Extract text from a PDF file page-by-page using PyMuPDF.

    Text is streamed to a .txt file to avoid memory issues with very large PDFs.

    :param pdf_path: Path to the input PDF file.
    :param text_output_path: Path where the extracted text file will be written.
    :return: Number of pages processed.
    """
    text_output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    num_pages = doc.page_count

    with text_output_path.open("w", encoding="utf-8") as txt_file:
        for page_index in range(num_pages):
            page = doc.load_page(page_index)
            text = page.get_text("text")
            if text:
                txt_file.write(text.strip() + "\n\n")

    doc.close()
    return num_pages


