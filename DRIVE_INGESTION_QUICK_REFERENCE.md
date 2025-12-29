# Google Drive Ingestion - Quick Reference

## API Endpoint

```
POST /ingest/drive?folder_id={FOLDER_ID}
```

## Example Usage

### cURL
```bash
curl -X POST "http://localhost:8000/ingest/drive?folder_id=1a2b3c4d5e6f7g8h9i0j"
```

### Python
```python
import requests

response = requests.post(
    "http://localhost:8000/ingest/drive",
    params={"folder_id": "1a2b3c4d5e6f7g8h9i0j"}
)
print(response.json())
```

### JavaScript (fetch)
```javascript
fetch('http://localhost:8000/ingest/drive?folder_id=1a2b3c4d5e6f7g8h9i0j', {
  method: 'POST'
})
.then(r => r.json())
.then(data => console.log(data));
```

## Response Format

```json
{
  "total_pdfs": 10,
  "processed": 8,
  "rejected": 2,
  "failed": 0,
  "processed_files": [
    {
      "file_name": "document.pdf",
      "file_id": "document",
      "number_of_pages": 25,
      "number_of_chunks": 45,
      "status": "ok"
    }
  ],
  "rejected_files": ["already_processed.pdf"],
  "failed_files": []
}
```

## Required Environment Variables

```env
GOOGLE_DRIVE_CREDENTIALS_PATH=/path/to/service-account-key.json
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key
```

## Required Supabase Table

```sql
CREATE TABLE processed_files (
    id BIGSERIAL PRIMARY KEY,
    drive_file_id TEXT UNIQUE NOT NULL,
    file_name TEXT NOT NULL,
    folder_path TEXT NOT NULL,
    processed_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Key Features

✅ **Idempotent**: Same file processed twice = rejected  
✅ **Recursive**: Processes all PDFs in subfolders  
✅ **Metadata Preserved**: Folder hierarchy stored  
✅ **Fail-Safe**: Only marks as processed after success  
✅ **Logging**: Clear logs for processed/rejected/failed files  

## Pipeline Flow

1. Authenticate with Google Drive (Service Account)
2. Recursively list all PDFs in folder
3. Check `processed_files` table for each PDF
4. If already processed → **REJECT** (log + skip)
5. If new → Download PDF bytes
6. Extract text → Reconstruct → Chunk → Embed
7. Store in FAISS + Supabase
8. Mark as processed in `processed_files` table

## Log Messages

- `REJECTED (already processed): filename.pdf` - File was skipped
- `PROCESSED: filename.pdf (45 chunks)` - File successfully processed
- `FAILED to process filename.pdf: error` - Processing failed (not marked as processed)

