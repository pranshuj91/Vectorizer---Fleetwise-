from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates

from services.pdf_loader import save_upload_file, extract_text_from_pdf
from services.text_chunker import chunk_text_file
from services.embedder import EmbeddingService


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
TEXT_DIR = DATA_DIR / "texts"
CHUNKS_DIR = DATA_DIR / "chunks"
VECTORS_DIR = DATA_DIR / "vectors"

# Maximum upload size: 1GB. The actual guard is implemented in save_upload_file
# which stops writing when this limit is exceeded.
MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024 * 1024  # 1GB


def ensure_directories() -> None:
    """
    Ensure that all required data directories exist.
    """
    for d in (UPLOAD_DIR, TEXT_DIR, CHUNKS_DIR, VECTORS_DIR):
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
    Upload a PDF, extract text, generate embeddings, and update FAISS index.
    Returns basic metadata about the processed file.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

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

    # Extract text from PDF page-by-page into a UTF-8 text file. Page order is
    # preserved because pages are processed sequentially.
    text_output_path = TEXT_DIR / f"{file_id}.txt"
    try:
        num_pages = extract_text_from_pdf(saved_pdf_path, text_output_path)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Failed to extract text from PDF.") from exc

    # Chunk text into 500-700 "token" chunks (approximate tokens by words) and
    # persist them as JSONL for later inspection/download.
    chunks_jsonl_path = CHUNKS_DIR / f"{file_id}.jsonl"
    chunks = chunk_text_file(
        text_file_path=text_output_path,
        target_chunk_size_tokens=600,
        overlap_tokens=50,
        jsonl_output_path=chunks_jsonl_path,
    )

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


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)


