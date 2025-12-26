#!/usr/bin/env python3
"""
Automatic File Upload Script for Vectorizer Fleetwise API

Usage:
    python auto_upload.py <file_path>
    python auto_upload.py <folder_path>  # Process all files in folder
    python auto_upload.py --watch <folder_path>  # Watch folder for new files
"""

import sys
import os
import requests
import time
from pathlib import Path
from typing import Optional

# ============================================
# CONFIGURATION - अपना domain यहाँ डालें
# ============================================
API_BASE_URL = os.getenv("VECTORIZER_API_URL", "https://your-domain.com")
# या local testing के लिए:
# API_BASE_URL = "http://localhost:8000"

SUPPORTED_EXTENSIONS = ['.pdf', '.json', '.csv', '.xls', '.xlsx']
MAX_FILE_SIZE_MB = 1024  # 1GB


def upload_file(file_path: str) -> Optional[dict]:
    """
    Upload और process एक file।
    
    Returns:
        dict: API response with file_id and processing details
        None: अगर error हुआ
    """
    file_path_obj = Path(file_path)
    
    if not file_path_obj.exists():
        print(f"❌ File not found: {file_path}")
        return None
    
    if not file_path_obj.is_file():
        print(f"❌ Not a file: {file_path}")
        return None
    
    ext = file_path_obj.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        print(f"⚠️  Unsupported file type: {ext}")
        return None
    
    file_size_mb = file_path_obj.stat().st_size / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        print(f"❌ File too large: {file_size_mb:.2f} MB (max: {MAX_FILE_SIZE_MB} MB)")
        return None
    
    print(f"\n📤 Uploading: {file_path_obj.name} ({file_size_mb:.2f} MB)")
    print(f"   URL: {API_BASE_URL}/upload")
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": (file_path_obj.name, f, "application/octet-stream")}
            
            # Large files के लिए timeout बढ़ाएं
            timeout = max(300, int(file_size_mb * 2))  # 2 seconds per MB, minimum 5 minutes
            
            response = requests.post(
                f"{API_BASE_URL}/upload",
                files=files,
                timeout=timeout
            )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success!")
            print(f"   File ID: {data.get('file_id')}")
            print(f"   Status: {data.get('status')}")
            
            if 'number_of_pages' in data:
                print(f"   Pages: {data.get('number_of_pages')}")
            if 'number_of_chunks' in data:
                print(f"   Chunks: {data.get('number_of_chunks')}")
            if 'number_of_blocks' in data:
                print(f"   Blocks: {data.get('number_of_blocks')}")
            
            if data.get('raw_download_url'):
                print(f"   Raw Text: {API_BASE_URL}{data['raw_download_url']}")
            if data.get('chunks_download_url'):
                print(f"   Chunks: {API_BASE_URL}{data['chunks_download_url']}")
            
            return data
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print(f"⏱️  Timeout: File too large or server slow")
        return None
    except requests.exceptions.ConnectionError:
        print(f"🔌 Connection Error: Check if API is running at {API_BASE_URL}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None


def process_folder(folder_path: str, recursive: bool = False):
    """
    Folder में सभी supported files को process करें।
    """
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"❌ Folder not found: {folder_path}")
        return
    
    if not folder.is_dir():
        print(f"❌ Not a directory: {folder_path}")
        return
    
    print(f"\n📁 Processing folder: {folder_path}")
    
    # Find all supported files
    if recursive:
        files = []
        for ext in SUPPORTED_EXTENSIONS:
            files.extend(folder.rglob(f"*{ext}"))
    else:
        files = []
        for ext in SUPPORTED_EXTENSIONS:
            files.extend(folder.glob(f"*{ext}"))
    
    if not files:
        print("⚠️  No supported files found")
        return
    
    print(f"📄 Found {len(files)} file(s)")
    
    success_count = 0
    for i, file_path in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] Processing: {file_path.name}")
        result = upload_file(str(file_path))
        if result:
            success_count += 1
        
        # Rate limiting - avoid overwhelming the server
        if i < len(files):
            time.sleep(1)
    
    print(f"\n✅ Completed: {success_count}/{len(files)} files processed successfully")


def watch_folder(folder_path: str):
    """
    Folder को watch करें और नई files automatically process करें।
    """
    print(f"👀 Watching folder: {folder_path}")
    print("   Press Ctrl+C to stop")
    
    processed_files = set()
    folder = Path(folder_path)
    
    try:
        while True:
            # Check for new files
            for ext in SUPPORTED_EXTENSIONS:
                for file_path in folder.glob(f"*{ext}"):
                    if str(file_path) not in processed_files:
                        print(f"\n🆕 New file detected: {file_path.name}")
                        result = upload_file(str(file_path))
                        if result:
                            processed_files.add(str(file_path))
            
            time.sleep(5)  # Check every 5 seconds
            
    except KeyboardInterrupt:
        print("\n\n👋 Stopped watching")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nUsage:")
        print("  python auto_upload.py <file_path>")
        print("  python auto_upload.py <folder_path>")
        print("  python auto_upload.py --watch <folder_path>")
        print("\nExample:")
        print("  python auto_upload.py document.pdf")
        print("  python auto_upload.py /path/to/documents")
        print("  python auto_upload.py --watch /path/to/documents")
        sys.exit(1)
    
    # Check for watch mode
    if sys.argv[1] == "--watch":
        if len(sys.argv) < 3:
            print("❌ Error: --watch requires a folder path")
            sys.exit(1)
        watch_folder(sys.argv[2])
        return
    
    path = sys.argv[1]
    path_obj = Path(path)
    
    if path_obj.is_file():
        # Single file
        upload_file(path)
    elif path_obj.is_dir():
        # Folder
        process_folder(path)
    else:
        print(f"❌ Path not found: {path}")
        sys.exit(1)


if __name__ == "__main__":
    main()

