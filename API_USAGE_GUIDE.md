# API Usage Guide - Vectorizer Fleetwise

## 🚀 Quick Start

आपका API deploy हो गया है। अब आप इसे programmatically use कर सकते हैं।

---

## 📍 Base URL

अपने deployed domain को use करें:
```
https://your-domain.com
```

या local testing के लिए:
```
http://localhost:8000
```

---

## 🔑 Main API Endpoint: File Upload

### **POST** `/upload`

यह endpoint automatically सब कुछ करता है:
- ✅ File upload करता है
- ✅ Text extract करता है (PDF/JSON/CSV/Excel)
- ✅ Semantic chunking करता है
- ✅ Embeddings generate करता है
- ✅ FAISS में store करता है
- ✅ Supabase में vectors save करता है

### Request Format

**Content-Type**: `multipart/form-data`

**Body**:
- `file`: Your file (PDF, JSON, CSV, Excel)
- Max size: 1GB

### Example: Using cURL

```bash
curl -X POST "https://your-domain.com/upload" \
  -F "file=@/path/to/your/document.pdf"
```

### Example: Using Python (requests)

```python
import requests

url = "https://your-domain.com/upload"

# PDF file upload
with open("document.pdf", "rb") as f:
    files = {"file": ("document.pdf", f, "application/pdf")}
    response = requests.post(url, files=files)

print(response.json())
```

### Example: Using JavaScript (fetch)

```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

fetch('https://your-domain.com/upload', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => {
  console.log('Upload successful:', data);
  console.log('File ID:', data.file_id);
  console.log('Chunks:', data.number_of_chunks);
})
.catch(error => console.error('Error:', error));
```

### Example: Using Postman

1. Method: **POST**
2. URL: `https://your-domain.com/upload`
3. Body → form-data
4. Key: `file` (type: File)
5. Value: Select your PDF/JSON/CSV/Excel file
6. Click **Send**

### Response Format

**Success Response (200 OK)**:
```json
{
  "file_name": "document.pdf",
  "file_id": "document_abc123",
  "number_of_pages": 10,
  "number_of_chunks": 5,
  "raw_exists": true,
  "chunks_exist": true,
  "raw_download_url": "/download/raw/document_abc123",
  "chunks_download_url": "/download/chunks/document_abc123",
  "status": "ok"
}
```

**For non-PDF files (JSON/CSV/Excel)**:
```json
{
  "file_name": "data.json",
  "file_id": "data_xyz789",
  "source_type": "json",
  "number_of_blocks": 15,
  "raw_exists": true,
  "chunks_exist": false,
  "raw_download_url": "/download/raw/data_xyz789",
  "chunks_download_url": null,
  "status": "ok"
}
```

**Error Responses**:

- `400 Bad Request`: Invalid file type or empty file
- `500 Internal Server Error`: Processing failed

---

## 📥 Download Endpoints

### **GET** `/download/raw/{file_id}`

Extracted raw text download करें।

**Example**:
```bash
curl "https://your-domain.com/download/raw/document_abc123" -o extracted_text.txt
```

### **GET** `/download/chunks/{file_id}`

Semantic chunks download करें (JSON format)।

**Example**:
```bash
curl "https://your-domain.com/download/chunks/document_abc123" -o chunks.json
```

---

## 🔍 Search Endpoint

### **POST** `/search`

Uploaded documents में semantic search करें।

**Request Format**:
- **Content-Type**: `application/x-www-form-urlencoded`
- **Body**: 
  - `query`: Your search query
  - `top_k`: Number of results (default: 5)

**Example: Using cURL**:
```bash
curl -X POST "https://your-domain.com/search" \
  -d "query=how to fix clutch errors&top_k=5"
```

**Example: Using Python**:
```python
import requests

url = "https://your-domain.com/search"
data = {
    "query": "how to fix clutch errors",
    "top_k": 5
}
response = requests.post(url, data=data)
results = response.json()
print(results)
```

**Response**:
```json
{
  "results": [
    {
      "score": 0.85,
      "file_name": "document.pdf",
      "chunk_index": 2,
      "section": "Clutch Calibration",
      "text": "To fix clutch calibration errors, first check..."
    }
  ],
  "status": "ok"
}
```

---

## 👀 Preview Endpoint

### **GET** `/preview/chunks/{file_id}?limit=10`

First N chunks को inspect करने के लिए।

**Example**:
```bash
curl "https://your-domain.com/preview/chunks/document_abc123?limit=10"
```

---

## 🎯 Complete Automation Example

### Python Script - Automatic File Processing

```python
import requests
import os
import time

# Configuration
API_BASE_URL = "https://your-domain.com"
FOLDER_PATH = "/path/to/your/documents"

def process_file(file_path):
    """Upload and process a single file"""
    print(f"Processing: {file_path}")
    
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f)}
        response = requests.post(f"{API_BASE_URL}/upload", files=files)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success! File ID: {data['file_id']}")
        print(f"   Chunks: {data.get('number_of_chunks', 0)}")
        return data['file_id']
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")
        return None

def process_folder(folder_path):
    """Process all PDF/JSON/CSV/Excel files in a folder"""
    supported_extensions = ['.pdf', '.json', '.csv', '.xls', '.xlsx']
    
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            ext = os.path.splitext(filename)[1].lower()
            if ext in supported_extensions:
                process_file(file_path)
                time.sleep(1)  # Rate limiting

# Run
if __name__ == "__main__":
    process_folder(FOLDER_PATH)
```

### JavaScript/Node.js - Automatic File Processing

```javascript
const fs = require('fs');
const FormData = require('form-data');
const axios = require('axios');
const path = require('path');

const API_BASE_URL = 'https://your-domain.com';
const FOLDER_PATH = '/path/to/your/documents';

async function processFile(filePath) {
  console.log(`Processing: ${filePath}`);
  
  const form = new FormData();
  form.append('file', fs.createReadStream(filePath));
  
  try {
    const response = await axios.post(`${API_BASE_URL}/upload`, form, {
      headers: form.getHeaders()
    });
    
    console.log(`✅ Success! File ID: ${response.data.file_id}`);
    console.log(`   Chunks: ${response.data.number_of_chunks || 0}`);
    return response.data.file_id;
  } catch (error) {
    console.error(`❌ Error: ${error.response?.status} - ${error.message}`);
    return null;
  }
}

async function processFolder(folderPath) {
  const supportedExtensions = ['.pdf', '.json', '.csv', '.xls', '.xlsx'];
  
  const files = fs.readdirSync(folderPath);
  
  for (const filename of files) {
    const filePath = path.join(folderPath, filename);
    const ext = path.extname(filename).toLowerCase();
    
    if (fs.statSync(filePath).isFile() && supportedExtensions.includes(ext)) {
      await processFile(filePath);
      await new Promise(resolve => setTimeout(resolve, 1000)); // Rate limiting
    }
  }
}

// Run
processFolder(FOLDER_PATH);
```

---

## 🔄 Webhook Integration (Future)

अगर आप चाहते हैं कि processing complete होने पर automatically notification मिले, तो webhook endpoint add कर सकते हैं।

---

## 📊 API Status & Health Check

### **GET** `/docs`

Interactive API documentation देखने के लिए:
```
https://your-domain.com/docs
```

### **GET** `/redoc`

Alternative API documentation:
```
https://your-domain.com/redoc
```

---

## ⚙️ Supported File Types

1. **PDF** (`.pdf`)
   - Full pipeline: Text extraction → Semantic repair → Chunking → Embeddings

2. **JSON** (`.json`)
   - Normalized to semantic blocks
   - Raw text extraction

3. **CSV** (`.csv`)
   - Row-by-row processing
   - Column headers included

4. **Excel** (`.xls`, `.xlsx`)
   - Sheet-by-sheet processing
   - Row-by-row with headers

---

## 🛡️ Error Handling

### Common Errors

1. **400 Bad Request**
   - Invalid file type
   - File too large (>1GB)
   - Empty file

2. **500 Internal Server Error**
   - PDF extraction failed
   - Embedding generation failed
   - Supabase connection failed

### Retry Logic Example

```python
import requests
import time

def upload_with_retry(file_path, max_retries=3):
    for attempt in range(max_retries):
        try:
            with open(file_path, "rb") as f:
                files = {"file": f}
                response = requests.post(
                    "https://your-domain.com/upload",
                    files=files,
                    timeout=300  # 5 minutes for large files
                )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 400:
                # Don't retry client errors
                raise Exception(f"Bad request: {response.text}")
            else:
                # Retry server errors
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Failed after {max_retries} attempts")
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                continue
            raise
    return None
```

---

## 📝 Notes

1. **File Size Limit**: Maximum 1GB per file
2. **Processing Time**: Large PDFs may take several minutes
3. **Rate Limiting**: Multiple files upload करते समय delay add करें
4. **API Keys**: Ensure `.env` में सभी API keys properly configured हैं

---

## 🎯 Quick Test

सबसे simple test:

```bash
# Replace with your actual domain
curl -X POST "https://your-domain.com/upload" \
  -F "file=@test.pdf"
```

अगर सब ठीक है, तो आपको JSON response मिलेगा with `file_id` और processing details।

---

**Happy Coding! 🚀**

