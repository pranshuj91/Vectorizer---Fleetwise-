# Google Drive Ingestion Setup Guide

## Overview

The Google Drive ingestion adapter allows you to automatically process PDFs from Google Drive folders into your RAG pipeline. It ensures idempotency by tracking processed files and rejecting duplicates.

## Prerequisites

1. **Google Cloud Project** with Drive API enabled
2. **Service Account** with Drive API access
3. **Supabase Table** for tracking processed files

## Step 1: Create Google Cloud Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Drive API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Drive API"
   - Click "Enable"

4. Create a Service Account:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "Service Account"
   - Fill in the service account details
   - Click "Create and Continue"
   - Skip role assignment (not needed for Drive API)
   - Click "Done"

5. Create and Download JSON Key:
   - Click on the created service account
   - Go to "Keys" tab
   - Click "Add Key" > "Create new key"
   - Select "JSON" format
   - Download the JSON file (e.g., `service-account-key.json`)

## Step 2: Share Google Drive Folder with Service Account

1. Open the Google Drive folder you want to ingest from
2. Click "Share" button
3. Add the service account email (found in the JSON file as `client_email`)
   - Example: `your-service-account@your-project.iam.gserviceaccount.com`
4. Grant **"Viewer"** permission (read-only is sufficient)
5. Click "Send"

**Important**: The service account must have access to all subfolders you want to process.

## Step 3: Configure Environment Variables

Add to your `.env` file:

```env
# Google Drive Service Account Credentials
GOOGLE_DRIVE_CREDENTIALS_PATH=/path/to/service-account-key.json
```

**Windows Example:**
```env
GOOGLE_DRIVE_CREDENTIALS_PATH=C:\Users\team\OneDrive\Desktop\Vectorizer---Fleetwise-\service-account-key.json
```

**Linux/Mac Example:**
```env
GOOGLE_DRIVE_CREDENTIALS_PATH=/home/user/project/service-account-key.json
```

## Step 4: Create Supabase Table for Processed Files

Run this SQL in your Supabase SQL Editor:

```sql
-- Table to track processed Google Drive files
CREATE TABLE IF NOT EXISTS processed_files (
    id BIGSERIAL PRIMARY KEY,
    drive_file_id TEXT UNIQUE NOT NULL,
    file_name TEXT NOT NULL,
    folder_path TEXT NOT NULL,
    processed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_processed_files_drive_file_id 
ON processed_files(drive_file_id);

-- Optional: Add comments
COMMENT ON TABLE processed_files IS 'Tracks Google Drive files that have been processed to prevent duplicates';
COMMENT ON COLUMN processed_files.drive_file_id IS 'Google Drive file ID (unique identifier)';
COMMENT ON COLUMN processed_files.folder_path IS 'Full folder path from Drive root (e.g., "Root/Subfolder")';
```

## Step 5: Get Google Drive Folder ID

1. Open the Google Drive folder in your browser
2. Look at the URL:
   ```
   https://drive.google.com/drive/folders/1a2b3c4d5e6f7g8h9i0j
   ```
3. The folder ID is the part after `/folders/`: `1a2b3c4d5e6f7g8h9i0j`

## Step 6: Run Ingestion

### Using API Endpoint

```bash
curl -X POST "http://localhost:8000/ingest/drive?folder_id=1a2b3c4d5e6f7g8h9i0j"
```

### Using Python

```python
import requests

response = requests.post(
    "http://localhost:8000/ingest/drive",
    params={"folder_id": "1a2b3c4d5e6f7g8h9i0j"}
)

print(response.json())
```

### Response Format

```json
{
  "total_pdfs": 10,
  "processed": 8,
  "rejected": 2,
  "failed": 0,
  "processed_files": [
    {
      "file_name": "document1.pdf",
      "file_id": "document1",
      "number_of_pages": 25,
      "number_of_chunks": 45,
      "status": "ok"
    },
    ...
  ],
  "rejected_files": [
    "already_processed.pdf",
    "duplicate.pdf"
  ],
  "failed_files": []
}
```

## How It Works

1. **Authentication**: Uses service account JSON key to authenticate
2. **Recursive Traversal**: Lists all PDFs in the folder and subfolders
3. **Deduplication Check**: For each PDF, checks `processed_files` table
4. **Processing**: If new, downloads PDF and runs through pipeline:
   - Text extraction
   - Semantic reconstruction
   - Chunking
   - Embedding generation
   - Storage in FAISS and Supabase
5. **Mark as Processed**: Only after successful completion, marks file in `processed_files`

## Idempotency Guarantee

- **Same file processed twice**: Rejected with log message "REJECTED (already processed)"
- **Re-running ingestion**: Only new files are processed
- **Failed files**: Not marked as processed, so they can be retried

## Troubleshooting

### Error: "GOOGLE_DRIVE_CREDENTIALS_PATH env var is required"

**Solution**: Set `GOOGLE_DRIVE_CREDENTIALS_PATH` in your `.env` file.

### Error: "Google Drive credentials file not found"

**Solution**: Check that the path in `.env` is correct and the file exists.

### Error: "Insufficient permissions"

**Solution**: Ensure the service account email has been shared with the folder (Viewer permission is enough).

### Error: "Failed to check processed_files table"

**Solution**: Verify that the `processed_files` table exists in Supabase and `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` are set correctly.

### No PDFs Found

**Solution**: 
- Verify the folder ID is correct
- Ensure PDFs are in the folder (not just folders)
- Check that the service account has access to the folder

## Security Notes

- **Service Account Key**: Keep the JSON key file secure and never commit it to git
- **Permissions**: Service account only needs "Viewer" access (read-only)
- **Environment Variables**: Never commit `.env` file with credentials

## Next Steps

After ingestion, your PDFs are:
- ✅ Extracted and stored as raw text
- ✅ Chunked semantically
- ✅ Embedded and stored in FAISS (local)
- ✅ Embedded and stored in Supabase pgvector (cloud)
- ✅ Tracked in `processed_files` table to prevent duplicates

You can now use the `/search` endpoint to query the ingested documents!

