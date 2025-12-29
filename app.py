# CRITICAL: Load .env FIRST before any other imports or logic
from pathlib import Path
import os
from dotenv import load_dotenv

# Force-load .env using absolute path
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

# Now import everything else
import uuid
import json
import logging
import re

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.pdf_loader import save_upload_file, extract_text_from_pdf
from services.text_reconstructor import reconstruct_text, save_reconstructed_document
from services.semantic_chunker import build_semantic_chunks, save_chunks_jsonl
from services.embedder import EmbeddingService
from services.json_extractor import extract_json_blocks
from services.csv_extractor import extract_csv_blocks
from services.excel_extractor import extract_excel_blocks
from services.vector_ingestion import ingest_chunks_to_supabase
from services.drive_ingest import ingest_drive_folder
DATA_DIR = BASE_DIR / "data"
STORAGE_DIR = BASE_DIR / "storage"

# PDF / text storage rooted under storage/
UPLOAD_DIR = STORAGE_DIR / "uploads"
TEXT_DIR = STORAGE_DIR / "raw_text"
CHUNKS_DIR = STORAGE_DIR / "chunks"

# Existing auxiliary dirs (kept for backward compatibility / non-PDF artifacts)
RECONSTRUCTED_DIR = DATA_DIR / "reconstructed"
NORMALIZED_DIR = DATA_DIR / "normalized"
VECTORS_DIR = DATA_DIR / "vectors"

# Maximum upload size: 1GB. The actual guard is implemented in save_upload_file
# which stops writing when this limit is exceeded.
MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024 * 1024  # 1GB


def ensure_directories() -> None:
    """
    Ensure that all required data directories exist.
    """
    for d in (UPLOAD_DIR, TEXT_DIR, CHUNKS_DIR, RECONSTRUCTED_DIR, NORMALIZED_DIR, VECTORS_DIR):
        d.mkdir(parents=True, exist_ok=True)


# Configure logging and validate critical env vars
logging.basicConfig(level=logging.INFO)
logging.info("Loaded .env from %s", ENV_PATH)

# Validate Supabase credentials (fail-fast if missing)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

logging.info("SUPABASE_URL loaded=%s", SUPABASE_URL is not None and SUPABASE_URL.strip() != "")
logging.info("SUPABASE_SERVICE_KEY loaded=%s", SUPABASE_SERVICE_KEY is not None and SUPABASE_SERVICE_KEY.strip() != "")

if not SUPABASE_URL or not SUPABASE_URL.strip():
    raise RuntimeError(
        "SUPABASE_URL is missing or empty. "
        f"Please set it in {ENV_PATH}"
    )

if not SUPABASE_SERVICE_KEY or not SUPABASE_SERVICE_KEY.strip():
    raise RuntimeError(
        "SUPABASE_SERVICE_KEY is missing or empty. "
        f"Please set it in {ENV_PATH}"
    )

ensure_directories()


def make_safe_file_id(stem: str) -> str:
    """
    Generate a URL- and filesystem-safe file identifier from an original stem.

    This avoids characters like spaces and '#' which can break URL routing
    or be interpreted as URL fragments.
    """
    # Replace any character that is not alphanumeric, '-' or '_' with '_'
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", stem)
    # Collapse consecutive underscores
    safe = re.sub(r"_+", "_", safe).strip("_")
    return safe or uuid.uuid4().hex

# max_request_size ensures Starlette will accept large uploads up to 1GB.
app = FastAPI(title="PDF Vectorizer", max_request_size=MAX_FILE_SIZE_BYTES)

# Configure CORS to allow requests from all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Initialize embedding service (loads model and FAISS index lazily)
embedding_service = EmbeddingService(VECTORS_DIR)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Serve the main HTML upload page.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/upload")
async def upload_pdf(
    # Note: we enforce the 1GB limit in save_upload_file; max_length on UploadFile
    # is not compatible with FastAPI/Pydantic here and would cause validation errors.
    file: UploadFile = File(..., description="PDF file to upload"),
):
    """
    Upload a file and route it to the appropriate ingestion pipeline.

    - PDF files go through the existing PDF → text → semantic repair → chunking → embeddings flow.
    - JSON/CSV/Excel files are normalized into semantic text blocks and written as JSONL.
    """
    filename = file.filename or ""
    lower_name = filename.lower()

    # Non-PDF ingestion path (kept completely separate from the PDF pipeline).
    if not lower_name.endswith(".pdf"):
        raw_bytes = await file.read()
        if not raw_bytes:
            raise HTTPException(status_code=400, detail="Empty file uploaded.")

        safe_stem = make_safe_file_id(Path(filename).stem)
        file_id = f"{safe_stem}_{uuid.uuid4().hex[:8]}"
        normalized_path = NORMALIZED_DIR / f"{file_id}.jsonl"

        if lower_name.endswith(".json"):
            blocks = extract_json_blocks(raw_bytes, filename)
        elif lower_name.endswith(".csv"):
            blocks = extract_csv_blocks(raw_bytes, filename)
        elif lower_name.endswith(".xls") or lower_name.endswith(".xlsx"):
            blocks = extract_excel_blocks(raw_bytes, filename)
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Only PDF, JSON, CSV, and Excel are allowed.",
            )

        if not blocks:
            return JSONResponse(
                {
                    "file_name": filename,
                    "file_id": file_id,
                    "source_type": "unknown",
                    "number_of_blocks": 0,
                    "raw_exists": False,
                    "chunks_exist": False,
                    "raw_download_url": None,
                    "chunks_download_url": None,
                    "status": "no_content",
                }
            )

        # Persist normalized JSONL blocks
        normalized_path.parent.mkdir(parents=True, exist_ok=True)
        with normalized_path.open("w", encoding="utf-8") as f:
            for block in blocks:
                f.write(json.dumps(block, ensure_ascii=False) + "\n")
        logging.info("Saved normalized blocks to %s", normalized_path)

        # Additionally persist a plain-text version of the structured content so
        # that /download/raw/{file_id} works consistently for non-PDF inputs.
        text_output_path = TEXT_DIR / f"{file_id}.txt"
        text_output_path.parent.mkdir(parents=True, exist_ok=True)
        with text_output_path.open("w", encoding="utf-8") as f_txt:
            for block in blocks:
                f_txt.write(str(block.get("text", "")))
                f_txt.write("\n\n")
        logging.info("Saved non-PDF raw text to %s", text_output_path)

        raw_exists = text_output_path.exists()
        # We currently don't expose a "chunks" download for non-PDF inputs,
        # so report chunks_exist as False and omit a chunks URL.
        return JSONResponse(
            {
                "file_name": filename,
                "file_id": file_id,
                "source_type": blocks[0]["source_type"],
                "number_of_blocks": len(blocks),
                "raw_exists": raw_exists,
                "chunks_exist": False,
                "raw_download_url": f"/download/raw/{file_id}" if raw_exists else None,
                "chunks_download_url": None,
                "status": "ok",
            }
        )

    # ---------------- PDF pipeline below: behavior unchanged ----------------

    if file.content_type not in ("application/pdf", "application/x-pdf"):
        # Strict content-type validation, but allow common variations
        raise HTTPException(status_code=400, detail="Invalid content type. Expected application/pdf.")

    # FastAPI/Starlette doesn't expose Content-Length directly here in a reliable way,
    # so the robust guard is to cap the number of bytes written during save.
    try:
        saved_pdf_path = await save_upload_file(
            upload_file=file,
            upload_dir=UPLOAD_DIR,
            max_size_bytes=MAX_FILE_SIZE_BYTES,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Failed to save uploaded file.") from exc

    # Use a sanitized version of the saved filename's stem as a stable file
    # identifier that is reused for text, chunks, and download URLs.
    file_id = make_safe_file_id(saved_pdf_path.stem)
    logging.info("Saved uploaded PDF to %s with file_id=%s", saved_pdf_path, file_id)

    # Extract raw text from PDF page-by-page into a UTF-8 text file. Page order
    # is preserved because pages are processed sequentially. This raw text file
    # is useful for debugging and external tooling.
    text_output_path = TEXT_DIR / f"{file_id}.txt"
    try:
        num_pages = extract_text_from_pdf(saved_pdf_path, text_output_path)
        logging.info("Saved raw text to %s", text_output_path)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Failed to extract text from PDF.") from exc

    # PHASE 1: Semantic text reconstruction. Fix line-wrapped sentences,
    # normalize paragraphs, and tag headings/paragraphs structurally.
    with text_output_path.open("r", encoding="utf-8") as f:
        raw_text = f.read()

    sections = reconstruct_text(raw_text)

    # Persist reconstructed sections for inspection. This file contains the
    # repaired, section-based document structure.
    reconstructed_output_path = RECONSTRUCTED_DIR / f"{file_id}.json"
    save_reconstructed_document(sections, str(reconstructed_output_path))

    # PHASE 2: Semantic chunking. Create RAG-ready chunks that stay within
    # a section, are paragraph-aligned, and maintain a small overlap.
    # Convert sections into the format expected by the chunker.
    chunker_sections = [
        {"section_title": s["title"], "content": s.get("paragraphs", [])} for s in sections
    ]
    chunks = build_semantic_chunks(chunker_sections, target_tokens=400, overlap_ratio=0.15)

    # Persist chunks as JSON to disk for download / inspection.
    chunks_path = CHUNKS_DIR / f"{file_id}.json"
    chunks_path.parent.mkdir(parents=True, exist_ok=True)
    with chunks_path.open("w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    logging.info("Saved chunks to %s", chunks_path)

    # Verify that raw text and chunks files exist; if not, fail fast so the UI
    # does not expose download buttons for missing artifacts.
    raw_text_exists = text_output_path.exists()
    chunks_exists = chunks_path.exists()

    if not raw_text_exists or not chunks_exists:
        raise HTTPException(
            status_code=500,
            detail="Internal error: failed to persist raw text or chunks to disk.",
        )

    if not chunks:
        return JSONResponse(
            {
                "file_name": saved_pdf_path.name,
                "file_id": file_id,
                "number_of_pages": num_pages,
                "number_of_chunks": 0,
                "raw_exists": raw_text_exists,
                "chunks_exist": chunks_exists,
                "raw_download_url": f"/download/raw/{file_id}",
                "chunks_download_url": f"/download/chunks/{file_id}",
                "status": "no_text_found",
            }
        )

    # Generate embeddings and update FAISS index
    try:
        embedding_service.add_documents(chunks=chunks, file_name=saved_pdf_path.name)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Failed to generate embeddings.") from exc

    # Additionally ingest vectors into Supabase pgvector using the configured
    # external embedding provider (if any). Failures here are logged but do not
    # affect the primary PDF pipeline.
    try:
        ingest_chunks_to_supabase(chunks=chunks, file_id=file_id, file_name=saved_pdf_path.name)
    except Exception as exc:  # pragma: no cover - defensive
        logging.warning("Supabase vector ingestion failed: %s", exc)

    return JSONResponse(
        {
            "file_name": saved_pdf_path.name,
            "file_id": file_id,
            "number_of_pages": num_pages,
            "number_of_chunks": len(chunks),
            "raw_exists": raw_text_exists,
            "chunks_exist": chunks_exists,
            "raw_download_url": f"/download/raw/{file_id}",
            "chunks_download_url": f"/download/chunks/{file_id}",
            "status": "ok",
        }
    )


@app.post("/search")
async def search_documents(query: str, top_k: int = 5):
    """
    Optional semantic search endpoint over all uploaded PDF chunks.
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    if top_k <= 0:
        raise HTTPException(status_code=400, detail="top_k must be positive.")

    if not embedding_service.has_index():
        return {"results": [], "status": "no_index"}

    try:
        results = embedding_service.search(query=query, top_k=top_k)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Search failed.") from exc

    return {"results": results, "status": "ok"}


@app.get("/download/raw/{file_id}")
async def download_raw_text(file_id: str):
    """
    Download the raw extracted text for a given file identifier.

    The file is streamed from disk using FileResponse to support very large
    payloads without loading the entire content into memory.
    """
    text_path = TEXT_DIR / f"{file_id}.txt"
    if not text_path.exists():
        logging.warning("Raw text download requested but file missing: %s", text_path)
        raise HTTPException(status_code=404, detail="Text file not found.")

    return FileResponse(text_path, media_type="text/plain; charset=utf-8", filename=text_path.name)


@app.get("/download/chunks/{file_id}")
async def download_chunks(file_id: str):
    """
    Download the JSONL chunks file for a given file identifier.

    Uses FileResponse so very large files (hundreds of MB or more) are streamed
    directly from disk.
    """
    chunks_path = CHUNKS_DIR / f"{file_id}.json"
    logging.info("Chunks download requested for %s", chunks_path)
    if not chunks_path.exists():
        logging.warning("Chunks download requested but file missing: %s", chunks_path)
        raise HTTPException(status_code=404, detail="Chunks file not found.")

    return FileResponse(
        chunks_path,
        media_type="application/json",
        filename=chunks_path.name,
    )


@app.get("/download/structured/{file_id}")
async def download_structured(file_id: str):
    """
    Download the structured JSON representation for a given file identifier.
    """
    structured_path = STRUCTURED_DIR / f"{file_id}.json"
    if not structured_path.exists():
        raise HTTPException(status_code=404, detail="Structured document not found.")

    return FileResponse(
        structured_path,
        media_type="application/json",
        filename=structured_path.name,
    )


@app.get("/preview/chunks/{file_id}")
async def preview_chunks(file_id: str, limit: int = 10):
    """
    Return the first N semantic chunks for quick inspection.

    Chunks are read from the JSONL file on disk without loading the entire file
    into memory, which keeps this endpoint safe for very large documents.
    """
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be positive.")

    chunks_path = CHUNKS_DIR / f"{file_id}.jsonl"
    if not chunks_path.exists():
        raise HTTPException(status_code=404, detail="Chunks file not found.")

    import json

    results = []
    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(results) >= limit:
                break

    return {"file_id": file_id, "limit": limit, "chunks": results}


class DriveIngestRequest(BaseModel):
    folder_id: str


@app.post("/ingest/drive")
async def ingest_google_drive(request: DriveIngestRequest):
    """
    Ingest all PDFs from a Google Drive folder into the pipeline.

    This endpoint:
    1. Recursively lists all PDFs in the specified folder
    2. Checks each PDF against the processed_files table
    3. Processes only new PDFs (rejects duplicates)
    4. Runs them through the full pipeline (extraction → chunking → embedding → Supabase)
    5. Marks successfully processed files as done

    :param request: JSON body with folder_id field.
                    folder_id can be extracted from: drive.google.com/drive/folders/{folder_id}
    :return: Summary with counts of processed, rejected, and failed files.
    """
    folder_id = request.folder_id.strip() if request.folder_id else ""
    if not folder_id:
        raise HTTPException(status_code=400, detail="folder_id is required.")

    try:
        result = ingest_drive_folder(
            folder_id=folder_id,
            base_dir=BASE_DIR,
            embedding_service=embedding_service,
        )
        return JSONResponse(result)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logging.error("Google Drive ingestion failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)


