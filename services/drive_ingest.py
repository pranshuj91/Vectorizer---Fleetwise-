from __future__ import annotations

import io
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from .processed_files import is_already_processed, mark_as_processed
from .text_reconstructor import reconstruct_text, save_reconstructed_document
from .semantic_chunker import build_semantic_chunks
from .vector_ingestion import ingest_chunks_to_supabase


def authenticate_drive(credentials_path: Optional[str] = None) -> Any:
    """
    Authenticate to Google Drive using a service account JSON key.

    :param credentials_path: Path to service account JSON file.
                             If None, reads from GOOGLE_DRIVE_CREDENTIALS_PATH env var.
    :return: Google Drive API service object.
    """
    if credentials_path is None:
        credentials_path = os.getenv("GOOGLE_DRIVE_CREDENTIALS_PATH")
        if not credentials_path:
            raise RuntimeError(
                "GOOGLE_DRIVE_CREDENTIALS_PATH env var is required for Google Drive authentication."
            )

    creds_path = Path(credentials_path)
    if not creds_path.exists():
        raise RuntimeError(f"Google Drive credentials file not found: {creds_path}")

    credentials = service_account.Credentials.from_service_account_file(
        str(creds_path),
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )

    service = build("drive", "v3", credentials=credentials)
    logging.info("Authenticated to Google Drive using service account")
    return service


def list_pdfs_recursive(service: Any, folder_id: str, parent_path: str = "") -> List[Dict[str, str]]:
    """
    Recursively list all PDF files in a Google Drive folder and its subfolders.

    :param service: Google Drive API service object.
    :param folder_id: Root folder ID to start traversal.
    :param parent_path: Internal path accumulator for folder hierarchy.
    :return: List of PDF file metadata dicts with keys:
             - drive_file_id: Google Drive file ID
             - file_name: PDF filename
             - folder_path: Full folder path from root (e.g., "Root/Subfolder")
    """
    pdfs: List[Dict[str, str]] = []

    def traverse_folder(folder_id: str, current_path: str) -> None:
        try:
            query = f"'{folder_id}' in parents and trashed=false"
            results = (
                service.files()
                .list(q=query, fields="files(id, name, mimeType)", pageSize=1000)
                .execute()
            )
            items = results.get("files", [])

            for item in items:
                item_id = item["id"]
                item_name = item["name"]
                mime_type = item.get("mimeType", "")

                if mime_type == "application/vnd.google-apps.folder":
                    new_path = f"{current_path}/{item_name}" if current_path else item_name
                    traverse_folder(item_id, new_path)
                elif mime_type == "application/pdf":
                    folder_path = current_path if current_path else "Root"
                    pdfs.append(
                        {
                            "drive_file_id": item_id,
                            "file_name": item_name,
                            "folder_path": folder_path,
                        }
                    )

        except Exception as exc:
            logging.warning("Error traversing folder %s: %s", folder_id, exc)

    traverse_folder(folder_id, parent_path)
    logging.info("Found %d PDF files in folder %s", len(pdfs), folder_id)
    return pdfs


def download_pdf(service: Any, file_id: str) -> bytes:
    """
    Download a PDF file from Google Drive as bytes.

    :param service: Google Drive API service object.
    :param file_id: Google Drive file ID.
    :return: PDF file content as bytes.
    """
    try:
        request = service.files().get_media(fileId=file_id)
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        pdf_bytes = file_buffer.getvalue()
        logging.info("Downloaded PDF file_id=%s (%d bytes)", file_id, len(pdf_bytes))
        return pdf_bytes
    except Exception as exc:
        logging.error("Failed to download PDF file_id=%s: %s", file_id, exc)
        raise


def extract_text_from_pdf_bytes(pdf_bytes: bytes, text_output_path: Path) -> int:
    """
    Extract text from PDF bytes and save to a text file.

    This is a wrapper around extract_text_from_pdf that works with bytes
    instead of a file path. It creates a temporary in-memory file.

    :param pdf_bytes: PDF file content as bytes.
    :param text_output_path: Path where extracted text will be saved.
    :return: Number of pages processed.
    """
    text_output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    num_pages = doc.page_count

    with text_output_path.open("w", encoding="utf-8") as txt_file:
        for page_index in range(num_pages):
            page = doc.load_page(page_index)
            text = page.get_text("text")
            if text:
                txt_file.write(text.strip() + "\n\n")

    doc.close()
    return num_pages


def _make_safe_file_id(stem: str) -> str:
    """
    Generate a URL- and filesystem-safe file identifier from an original stem.
    """
    import re
    import uuid

    safe = re.sub(r"[^A-Za-z0-9_-]", "_", stem)
    safe = re.sub(r"_+", "_", safe).strip("_")
    return safe or uuid.uuid4().hex


def process_pdf_from_drive(
    pdf_bytes: bytes,
    file_id: str,
    file_name: str,
    folder_path: str,
    base_dir: Path,
    embedding_service: Any,
) -> Dict[str, Any]:
    """
    Process a PDF from Google Drive through the full pipeline.

    This function replicates the exact pipeline used in app.py for manual uploads:
    1. Extract text from PDF
    2. Reconstruct text semantically
    3. Build semantic chunks
    4. Generate embeddings and store in FAISS
    5. Ingest into Supabase

    :param pdf_bytes: PDF file content as bytes.
    :param file_id: Safe file identifier (sanitized filename).
    :param file_name: Original PDF filename.
    :param folder_path: Full folder path from Drive root.
    :param base_dir: Base directory for storage paths.
    :param embedding_service: EmbeddingService instance for FAISS.
    :return: Processing result dict with status and metadata.
    """
    safe_file_id = _make_safe_file_id(Path(file_name).stem)
    text_output_path = base_dir / "storage" / "raw_text" / f"{safe_file_id}.txt"
    reconstructed_path = base_dir / "data" / "reconstructed" / f"{safe_file_id}.json"
    chunks_path = base_dir / "storage" / "chunks" / f"{safe_file_id}.json"

    try:
        num_pages = extract_text_from_pdf_bytes(pdf_bytes, text_output_path)
        logging.info("Extracted text from PDF: %s (%d pages)", file_name, num_pages)

        with text_output_path.open("r", encoding="utf-8") as f:
            raw_text = f.read()

        sections = reconstruct_text(raw_text)
        save_reconstructed_document(sections, str(reconstructed_path))

        chunker_sections = [
            {"section_title": s["title"], "content": s.get("paragraphs", [])} for s in sections
        ]
        chunks = build_semantic_chunks(chunker_sections, target_tokens=400, overlap_ratio=0.15)

        chunks_path.parent.mkdir(parents=True, exist_ok=True)
        with chunks_path.open("w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)
        logging.info("Saved %d chunks to %s", len(chunks), chunks_path)

        if not chunks:
            return {
                "file_name": file_name,
                "file_id": safe_file_id,
                "number_of_pages": num_pages,
                "number_of_chunks": 0,
                "status": "no_text_found",
            }

        embedding_service.add_documents(chunks=chunks, file_name=file_name)

        metadata = {
            "source": "google_drive",
            "folder_path": folder_path,
            "file_name": file_name,
            "drive_file_id": file_id,
        }
        ingest_chunks_to_supabase(chunks=chunks, file_id=safe_file_id, file_name=file_name)

        return {
            "file_name": file_name,
            "file_id": safe_file_id,
            "number_of_pages": num_pages,
            "number_of_chunks": len(chunks),
            "status": "ok",
        }

    except Exception as exc:
        logging.error("Failed to process PDF %s: %s", file_name, exc)
        raise


def ingest_drive_folder(
    folder_id: str,
    base_dir: Path,
    embedding_service: Any,
    credentials_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ingest all PDFs from a Google Drive folder into the pipeline.

    This is the main entry point for Google Drive ingestion. It:
    1. Authenticates to Google Drive
    2. Recursively lists all PDFs in the folder
    3. Checks each PDF against processed_files table
    4. Processes only new PDFs through the full pipeline
    5. Marks successfully processed files as done

    :param folder_id: Google Drive folder ID to ingest from.
    :param base_dir: Base directory for storage paths.
    :param embedding_service: EmbeddingService instance for FAISS.
    :param credentials_path: Optional path to service account JSON.
                             If None, reads from GOOGLE_DRIVE_CREDENTIALS_PATH env var.
    :return: Summary dict with counts of processed, rejected, and failed files.
    """
    service = authenticate_drive(credentials_path)
    pdfs = list_pdfs_recursive(service, folder_id)

    processed_count = 0
    rejected_count = 0
    failed_count = 0
    processed_files: List[Dict[str, Any]] = []
    rejected_files: List[str] = []
    failed_files: List[Dict[str, str]] = []

    for pdf_info in pdfs:
        drive_file_id = pdf_info["drive_file_id"]
        file_name = pdf_info["file_name"]
        folder_path = pdf_info["folder_path"]

        if is_already_processed(drive_file_id):
            logging.info("REJECTED (already processed): %s", file_name)
            rejected_count += 1
            rejected_files.append(file_name)
            continue

        try:
            pdf_bytes = download_pdf(service, drive_file_id)
            result = process_pdf_from_drive(
                pdf_bytes=pdf_bytes,
                file_id=drive_file_id,
                file_name=file_name,
                folder_path=folder_path,
                base_dir=base_dir,
                embedding_service=embedding_service,
            )

            mark_as_processed(drive_file_id, file_name, folder_path)
            processed_count += 1
            processed_files.append(result)
            logging.info("PROCESSED: %s (%d chunks)", file_name, result.get("number_of_chunks", 0))

        except Exception as exc:
            logging.error("FAILED to process %s: %s", file_name, exc)
            failed_count += 1
            failed_files.append({"file_name": file_name, "error": str(exc)})

    return {
        "total_pdfs": len(pdfs),
        "processed": processed_count,
        "rejected": rejected_count,
        "failed": failed_count,
        "processed_files": processed_files,
        "rejected_files": rejected_files,
        "failed_files": failed_files,
    }

