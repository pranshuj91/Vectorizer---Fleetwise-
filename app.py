from pathlib import Path
import uuid
import json

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates

from services.pdf_loader import save_upload_file, extract_text_from_pdf
from services.text_reconstructor import reconstruct_text, save_reconstructed_document
from services.semantic_chunker import build_semantic_chunks, save_chunks_jsonl
from services.embedder import EmbeddingService
from services.json_extractor import extract_json_blocks
from services.csv_extractor import extract_csv_blocks
from services.excel_extractor import extract_excel_blocks


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
TEXT_DIR = DATA_DIR / "texts"
RECONSTRUCTED_DIR = DATA_DIR / "reconstructed"
CHUNKS_DIR = DATA_DIR / "chunks"
NORMALIZED_DIR = DATA_DIR / "normalized"
VECTORS_DIR = DATA_DIR / "vectors"

# Maximum upload size: 1GB. The actual guard is implemented in save_upload_file
# which stops writing when this limit is exceeded.
MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024 * 1024  # 1GB


def ensure_directories() -> None:
    """
    Ensure that all required data directories exist.
    """
    for d in (UPLOAD_DIR, TEXT_DIR, RECONSTRUCTED_DIR, CHUNKS_DIR, NORMALIZED_DIR, VECTORS_DIR):
        d.mkdir(parents=True, exist_ok=True)


ensure_directories()

# max_request_size ensures Starlette will accept large uploads up to 1GB.
app = FastAPI(title="PDF Vectorizer", max_request_size=MAX_FILE_SIZE_BYTES)

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

        file_id = f"{Path(filename).stem}_{uuid.uuid4().hex[:8]}"
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
                    "status": "no_content",
                }
            )

        normalized_path.parent.mkdir(parents=True, exist_ok=True)
        with normalized_path.open("w", encoding="utf-8") as f:
            for block in blocks:
                f.write(json.dumps(block, ensure_ascii=False) + "\n")

        return JSONResponse(
            {
                "file_name": filename,
                "file_id": file_id,
                "source_type": blocks[0]["source_type"],
                "number_of_blocks": len(blocks),
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

    # Use the stem of the saved filename as a stable file identifier that is
    # reused for text, chunks, and vector metadata.
    file_id = saved_pdf_path.stem

    # Extract raw text from PDF page-by-page into a UTF-8 text file. Page order
    # is preserved because pages are processed sequentially. This raw text file
    # is useful for debugging and external tooling.
    text_output_path = TEXT_DIR / f"{file_id}.txt"
    try:
        num_pages = extract_text_from_pdf(saved_pdf_path, text_output_path)
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

    # Persist chunks as JSONL for later inspection/download.
    chunks_jsonl_path = CHUNKS_DIR / f"{file_id}.jsonl"
    save_chunks_jsonl(chunks, chunks_jsonl_path)

    if not chunks:
        return JSONResponse(
            {
                "file_name": saved_pdf_path.name,
                "file_id": file_id,
                "number_of_pages": num_pages,
                "number_of_chunks": 0,
                "status": "no_text_found",
            }
        )

    # Generate embeddings and update FAISS index
    try:
        embedding_service.add_documents(chunks=chunks, file_name=saved_pdf_path.name)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Failed to generate embeddings.") from exc

    return JSONResponse(
        {
            "file_name": saved_pdf_path.name,
            "file_id": file_id,
            "number_of_pages": num_pages,
            "number_of_chunks": len(chunks),
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


@app.get("/download/text/{file_id}")
async def download_raw_text(file_id: str):
    """
    Download the raw extracted text for a given file identifier.

    The file is streamed from disk using FileResponse to support very large
    payloads without loading the entire content into memory.
    """
    text_path = TEXT_DIR / f"{file_id}.txt"
    if not text_path.exists():
        raise HTTPException(status_code=404, detail="Text file not found.")

    return FileResponse(
        text_path,
        media_type="text/plain; charset=utf-8",
        filename=text_path.name,
    )


@app.get("/download/chunks/{file_id}")
async def download_chunks(file_id: str):
    """
    Download the JSONL chunks file for a given file identifier.

    Uses FileResponse so very large files (hundreds of MB or more) are streamed
    directly from disk.
    """
    chunks_path = CHUNKS_DIR / f"{file_id}.jsonl"
    if not chunks_path.exists():
        raise HTTPException(status_code=404, detail="Chunks file not found.")

    # application/jsonl is non-standard; application/json is widely supported.
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


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)


