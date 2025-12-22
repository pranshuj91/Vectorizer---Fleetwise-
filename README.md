# PDF Vectorizer – FastAPI + FAISS

Browser-based PDF upload and vectorization service built with FastAPI, PyMuPDF, SentenceTransformers, and FAISS.

## Features
- **PDF upload**: Accepts PDF files up to 500MB via a web UI.
- **Text extraction**: Streams text page-by-page from PDFs using PyMuPDF.
- **Chunking**: Splits extracted text into ~600-token overlapping chunks with small overlap for context.
- **Embeddings**: Uses `sentence-transformers/all-MiniLM-L6-v2` to embed chunks.
- **Vector store**: Persists embeddings in a FAISS (CPU) index plus JSON metadata under `data/vectors/`.
- **Semantic search (optional)**: `/search` endpoint over all stored chunks.

## Project Structure
- `app.py` – FastAPI application, upload and search endpoints, HTML index route.
- `services/pdf_loader.py` – Streaming PDF saving and text extraction.
- `services/text_chunker.py` – Token-based text file chunking.
- `services/embedder.py` – Embedding model + FAISS index and metadata management.
- `templates/index.html` – Minimal HTML+JS UI for upload and search.
- `data/uploads/` – Stored PDFs.
- `data/texts/` – Extracted text files.
- `data/vectors/` – FAISS index + metadata JSON.

## Installation
```bash
python -m venv .venv
.venv\Scripts\activate  # On Windows

pip install -r requirements.txt
```

## Running the App
```bash
uvicorn app:app --reload
```

Then open `http://127.0.0.1:8000/` in your browser to access the upload UI.
