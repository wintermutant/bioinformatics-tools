# Task Runner Decoupling + SFTP File Download

## Overview

These changes decouple the SSH task runner from Margie-specific logic and add SFTP-based file browsing/downloading for job output files.

## What Changed

### 1. Generic Task Runner (`ssh.py`)

Previously, `run_margie_task()` had the SSH command hardcoded inside it alongside all the log-parsing logic. Now:

- **`run_ssh_task(job_id, command)`** — generic function that accepts any command string. Handles log streaming, SLURM job ID parsing, Snakemake progress tracking, and phase updates.
- **`run_margie`** endpoint just constructs the command and passes it to `run_ssh_task`. This makes it easy to add new workflow endpoints (e.g. a different pipeline) without duplicating the task runner logic.

### 2. Working Directory Tracking (`ssh_slurm.py` + `ssh.py`)

`submit_ssh_job()` creates a timestamped working directory on Negishi (`/depot/lindems/data/margie/tests/{timestamp}`), but previously didn't expose it to the caller.

Now it yields a metadata line as the first output:
```
__WORKDIR__:/depot/lindems/data/margie/tests/2025-01-15-1430
```

`run_ssh_task` detects this prefix and stores it in `jobs[job_id]["work_dir"]`. This value is returned in the `job_status` response and used by the file listing/download endpoints.

### 3. SFTP File Operations (`ssh_slurm.py`)

Two new functions using paramiko's SFTP support:

- **`list_remote_dir(remote_path)`** — Returns `[{name, type, size}]` for all entries in a directory.
- **`stream_remote_file(remote_path)`** — Generator yielding 8KB chunks of a remote file. Used for streaming downloads without loading entire files into memory.

### 4. File Listing + Download Endpoints (`ssh.py`)

**`GET /v1/ssh/job_files/{job_id}?subdir=`**
- Lists files in the job's working directory via SFTP
- Optional `subdir` query param to browse subdirectories (e.g. `?subdir=prodigal`)
- Returns `{work_dir, subdir, entries: [{name, type, size}]}`

**`GET /v1/ssh/download_file/{job_id}?path=`**
- Streams a file from the job's working directory
- `path` is relative to `work_dir` (e.g. `prodigal/genome.faa`)
- Returns with `Content-Disposition: attachment` header

Both endpoints validate paths to prevent directory traversal attacks (rejects `..` segments and absolute paths).

### 5. Frontend File Browser (`+page.svelte`)

Replaced the hardcoded mock file list with a real file browser:

- Auto-fetches files from `/job_files/` when the job completes
- Directories are clickable — navigates into subdirectories
- "Back" button (..`) to navigate up
- Files show size and a "Download" link
- Section only appears when `work_dir` is available
- Shows "Files will be available after the job completes" while running

## Files Modified

| File | Repo | Changes |
|------|------|---------|
| `bioinformatics_tools/utilities/ssh_slurm.py` | backend | Yield `__WORKDIR__`, add `list_remote_dir()`, `stream_remote_file()` |
| `bioinformatics_tools/api/routers/ssh.py` | backend | Extract `run_ssh_task()`, add `/job_files/`, `/download_file/` endpoints |
| `margie-fe/src/routes/jobs/[jobid]/+page.svelte` | frontend | Real file listing with navigation and downloads |

## Architecture Notes

### Thread Safety

The `jobs = {}` dict and `ThreadPoolExecutor(max_workers=4)` are kept in-memory in the FastAPI process. This works because:

- Each job gets exactly one worker thread, so there's no concurrent writes to the same job's logs
- CPython's GIL prevents dict corruption from concurrent access
- The SLURM status checker daemon thread reads/writes `slurm_jobs` on the same dict, but worst case it misses a newly added job for one polling cycle

**Limitation**: If you run multiple uvicorn workers (`--workers N`), each gets its own `jobs` dict. At that point you'd need Redis or a database for shared job state. For single-worker dev, this is fine.

### Security

The download endpoint validates the `path` parameter:
- Rejects absolute paths (starting with `/`)
- Rejects directory traversal (`..` in any path segment)
- Only allows access to files within the job's `work_dir`
