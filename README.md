# PDF Vectorizer – FastAPI + FAISS

Browser-based PDF upload and vectorization service built with FastAPI, PyMuPDF, SentenceTransformers, and FAISS.

## Features
- **PDF upload**: Accepts PDF files up to 1GB via a web UI.
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

## Installation (Fresh Ubuntu machine)

These steps assume a brand new Ubuntu system with nothing installed.

1. **Install system packages (Python, git, build tools)**

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git build-essential
```

2. **Clone this repository**

Replace the URL with your own Git remote:

```bash
cd ~
git clone https://github.com/your-username/your-repo.git vectorizer-fleetwise
cd vectorizer-fleetwise
```

3. **Create and activate a virtual environment**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

4. **Install Python dependencies**

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Running the App

With the virtual environment activated in the project root:

```bash
uvicorn app:app --reload
```

Then open `http://127.0.0.1:8000/` in your browser to access the upload UI.
