# Git Repository Cleanup Instructions

## ✅ Status: Cleanup Complete

All runtime data files have been removed from git tracking. The repository is now clean and ready for push.

## What Was Done

1. ✅ Updated `.gitignore` to exclude all runtime directories and file types
2. ✅ Removed `data/` directory from git tracking (files remain on disk)
3. ✅ Removed `storage/` directory from git tracking (files remain on disk)
4. ✅ Removed all tracked PDF, JSONL, FAISS, TXT, and JSON files from data/ and storage/

## Next Steps

### Commit the Changes

```bash
git commit -m "Remove runtime data from git tracking

- Remove data/ and storage/ directories
- Remove tracked PDF, JSONL, FAISS files
- Update .gitignore to prevent future tracking
- Files remain on local disk, only removed from git"
```

### Push to Repository

**If this is a new branch:**

```bash
git push origin <your-branch-name>
```

**If you've already pushed and need to update the remote:**

```bash
# Use --force-with-lease for safety (prevents overwriting others' work)
git push --force-with-lease origin <your-branch-name>
```

**Warning**: `--force-with-lease` is safer than `--force` but still overwrites remote history. Only use if you're sure no one else has pushed to this branch.

---

## Reference: Manual Cleanup Steps (Already Completed)

### Option 1: Using the cleanup script (Linux/Mac/Git Bash)

```bash
chmod +x cleanup_git.sh
./cleanup_git.sh
```

### Option 2: Manual cleanup (Windows PowerShell)

Run these commands in PowerShell from the project root:

```powershell
# Remove data/ directory from git tracking (keeps files on disk)
git rm -r --cached data/

# Remove storage/ directory from git tracking (keeps files on disk)
git rm -r --cached storage/

# Remove any tracked PDF files
git rm --cached "*.pdf"
git rm --cached "data/**/*.pdf"
git rm --cached "storage/**/*.pdf"

# Remove any tracked JSONL files
git rm --cached "*.jsonl"
git rm --cached "data/**/*.jsonl"
git rm --cached "storage/**/*.jsonl"

# Remove any tracked FAISS files
git rm --cached "*.faiss"
git rm --cached "data/**/*.faiss"

# Remove any tracked .txt files in data/ or storage/
git rm --cached "data/**/*.txt"
git rm --cached "storage/**/*.txt"

# Remove any tracked .json files in data/ or storage/
git rm --cached "data/**/*.json"
git rm --cached "storage/**/*.json"

# Stage the updated .gitignore
git add .gitignore
```

### Verify Changes

```bash
git status
```

You should see:
- `data/` and `storage/` directories marked as deleted (from git)
- `.gitignore` marked as modified
- Files still exist on your disk (check with `ls data/` or `dir data`)

### Commit the Cleanup

```bash
git commit -m "Remove runtime data from git tracking

- Remove data/ and storage/ directories
- Remove tracked PDF, JSONL, FAISS files
- Update .gitignore to prevent future tracking
- Files remain on local disk, only removed from git"
```

### Push to Repository

**If this is a new branch or you haven't pushed yet:**

```bash
git push origin <your-branch-name>
```

**If you've already pushed and need to update the remote:**

```bash
# Use --force-with-lease for safety (prevents overwriting others' work)
git push --force-with-lease origin <your-branch-name>
```

**Warning**: `--force-with-lease` is safer than `--force` but still overwrites remote history. Only use if you're sure no one else has pushed to this branch.

## What Gets Removed from Git

- ✅ `data/` directory (all subdirectories: chunks, normalized, reconstructed, sections, structured, texts, uploads, vectors)
- ✅ `storage/` directory (all subdirectories: chunks, raw_text, uploads)
- ✅ All `.pdf` files
- ✅ All `.jsonl` files
- ✅ All `.faiss` files
- ✅ All `.txt` files in data/ or storage/
- ✅ All `.json` files in data/ or storage/

## What Stays in Git

- ✅ Source code (`.py` files)
- ✅ Templates (`templates/index.html`)
- ✅ Configuration files (`requirements.txt`, `README.md`)
- ✅ `.gitignore` (updated)

## What Remains on Your Disk

**Important**: All files remain on your local disk. Only git tracking is removed. Your application will continue to work normally.

## Verification

After cleanup, verify:

1. **Files still exist locally:**
   ```bash
   ls data/
   ls storage/
   ```

2. **Git no longer tracks them:**
   ```bash
   git ls-files | grep -E "(data/|storage/|\.pdf|\.jsonl|\.faiss)"
   ```
   Should return nothing (or only files that should be tracked).

3. **Repository size reduced:**
   ```bash
   git count-objects -vH
   ```

## Future Prevention

The updated `.gitignore` will prevent these files from being tracked in the future. Always check `git status` before committing to ensure no runtime files are accidentally staged.

