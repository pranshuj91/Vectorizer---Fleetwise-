# 🚀 API Quick Start Guide

## सबसे Simple तरीका

### 1. Single File Upload

**cURL**:
```bash
curl -X POST "https://your-domain.com/upload" \
  -F "file=@document.pdf"
```

**Python**:
```python
import requests

response = requests.post(
    "https://your-domain.com/upload",
    files={"file": open("document.pdf", "rb")}
)

print(response.json())
```

**JavaScript**:
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

fetch('https://your-domain.com/upload', {
  method: 'POST',
  body: formData
})
.then(r => r.json())
.then(data => console.log(data));
```

### 2. Automatic Folder Processing

**Python Script**:
```bash
python auto_upload.py /path/to/your/documents
```

या single file:
```bash
python auto_upload.py document.pdf
```

### 3. Response Format

```json
{
  "file_id": "document_abc123",
  "number_of_chunks": 5,
  "status": "ok",
  "raw_download_url": "/download/raw/document_abc123",
  "chunks_download_url": "/download/chunks/document_abc123"
}
```

## 📍 Main Endpoint

**POST** `https://your-domain.com/upload`

यह endpoint automatically:
- ✅ File upload करता है
- ✅ Text extract करता है
- ✅ Chunks बनाता है
- ✅ Embeddings generate करता है
- ✅ Supabase में save करता है

## 🔍 Search

```bash
curl -X POST "https://your-domain.com/search" \
  -d "query=your search query&top_k=5"
```

## 📥 Download

```bash
# Raw text
curl "https://your-domain.com/download/raw/{file_id}" -o text.txt

# Chunks
curl "https://your-domain.com/download/chunks/{file_id}" -o chunks.json
```

## ⚙️ Configuration

Script में अपना domain set करें:
```python
API_BASE_URL = "https://your-domain.com"
```

या environment variable:
```bash
export VECTORIZER_API_URL="https://your-domain.com"
python auto_upload.py document.pdf
```

---

**That's it! 🎉**

