"""
Fasta file processing endpoints
"""
import asyncio
import json
import logging
import os
import datetime
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pymongo import MongoClient

from bioinformatics_tools.utilities import ssh_slurm

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/ssh", tags=["ssh"])

MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:password123@localhost:27017/")
client = MongoClient(MONGO_URI)
db = client['biotools']
collection = db['dane_entries']


class DaneEntry(BaseModel):
    value: str


# Endpoints
@router.get("/health")
async def health_check():
    """Test endpoint to verify API is working"""
    return {"status": "success"}
    

@router.get("/entries")
async def get_dane_entries():
    """Get all dane entries as JSON"""
    entries = list(collection.find({}, {"_id": 0, "value": 1, "timestamp": 1}).sort("timestamp", -1))
    return {"entries": entries}


@router.post("/entries")
async def create_dane_entry(entry: DaneEntry):
    '''Keep as an example for adding to mongodb'''
    from datetime import datetime
    """Create a new dane entry"""
    new_entry = {
        "value": entry.value,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    collection.insert_one(new_entry)
    return {"success": True, "entry": {"value": new_entry["value"], "timestamp": new_entry["timestamp"]}}


class SlurmSend(BaseModel):
    script: str


class GenomeSend(BaseModel):
    genome_path: str

@router.post("/run_slurm")
async def run_slurm(content: SlurmSend):
    """Submit a SLURM job and return the job ID immediately"""
    job_id = ssh_slurm.submit_slurm_job(script_content=content.script)
    print(f'Inside of run_slurm, job id: {job_id}')
    return {"success": True, "job_id": job_id, "message": "Job submitted successfully"}


@router.post("/run_ssh")
async def run_shh(content: SlurmSend):
    """Submit a SLURM job and return the job ID immediately"""
    LOGGER.info('Running run_shh')
    std_txt = ssh_slurm.submit_ssh_job(cmd=content.script)
    LOGGER.info('Inside of run_shh. std_txt: %s', std_txt)
    return {"success": True, "std_txt": std_txt, "message": "Job submitted successfully"}

# Job storage and executor
jobs = {}
executor = ThreadPoolExecutor(max_workers=4)

# Regex patterns for parsing SLURM job IDs from Snakemake log output
SLURM_SUBMIT_RE = re.compile(r'SLURM jobid (\d+) \(log:.*?/slurm_logs/(?:rule_|group_[^_]+_)(\w+)/')
SLURM_SUBMIT_FALLBACK_RE = re.compile(r'SLURM jobid (\d+)')
# Matches: "4 of 4 steps (100%) done" (with possible ANSI color codes)
STEPS_PROGRESS_RE = re.compile(r'(\d+) of (\d+) steps \((\d+)%\) done')


def _slurm_status_checker(job_id: str):
    """Daemon thread that periodically checks SLURM job statuses."""
    while jobs.get(job_id, {}).get("status") == "running":
        slurm_jobs = jobs[job_id].get("slurm_jobs", [])
        active_ids = [sj["job_id"] for sj in slurm_jobs if sj["status"] not in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT")]
        if active_ids:
            try:
                statuses = ssh_slurm.check_multiple_slurm_jobs(active_ids)
                for sj in slurm_jobs:
                    if sj["job_id"] in statuses:
                        sj["status"] = statuses[sj["job_id"]]["state"]
                        sj["time"] = statuses[sj["job_id"]]["time"]
            except Exception as e:
                LOGGER.warning("SLURM status check failed: %s", e)
        # Wait 15 seconds between checks
        for _ in range(15):
            if jobs.get(job_id, {}).get("status") != "running":
                break
            time.sleep(1)


def run_ssh_task(job_id: str, command: str):
    """Generic SSH task runner with log parsing, SLURM tracking, and progress parsing."""
    jobs[job_id]["status"] = "running"
    jobs[job_id]["phase"] = "Submitting to Negishi (SSH)"
    jobs[job_id]["logs"] = ""

    # Start SLURM status checker daemon thread
    checker = threading.Thread(target=_slurm_status_checker, args=(job_id,), daemon=True)
    checker.start()

    try:
        for line in ssh_slurm.submit_ssh_job(cmd=command):
            # Detect work_dir metadata from submit_ssh_job
            if line.startswith("__WORKDIR__:"):
                jobs[job_id]["work_dir"] = line.split(":", 1)[1]
                continue

            # Parse container metadata from bapptainer log lines
            if "__CONTAINER__:" in line:
                try:
                    container_json = line.split("__CONTAINER__:", 1)[1]
                    jobs[job_id]["containers"].append(json.loads(container_json))
                except (json.JSONDecodeError, IndexError):
                    pass

            jobs[job_id]["logs"] += line + "\n"

            # Parse SLURM job IDs as they appear in the log stream
            match = SLURM_SUBMIT_RE.search(line)
            if match:
                slurm_id, rule_name = match.groups()
                jobs[job_id]["slurm_jobs"].append({
                    "job_id": slurm_id, "rule": rule_name,
                    "status": "SUBMITTED", "time": "00:00:00"
                })
            elif SLURM_SUBMIT_FALLBACK_RE.search(line):
                fallback = SLURM_SUBMIT_FALLBACK_RE.search(line)
                slurm_id = fallback.group(1)
                jobs[job_id]["slurm_jobs"].append({
                    "job_id": slurm_id, "rule": "unknown",
                    "status": "SUBMITTED", "time": "00:00:00"
                })

            # Parse Snakemake step progress (e.g. "2 of 4 steps (50%) done")
            progress_match = STEPS_PROGRESS_RE.search(line)
            if progress_match:
                done, total, pct = progress_match.groups()
                jobs[job_id]["steps_done"] = int(done)
                jobs[job_id]["steps_total"] = int(total)
                jobs[job_id]["progress"] = int(pct)

            # Update phase based on output
            if "snakemake" in line.lower():
                jobs[job_id]["phase"] = "Running Snakemake"

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["phase"] = "Done"
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["logs"] += f"\nError: {str(e)}"


@router.post("/run_margie")
async def run_margie(genome_data: GenomeSend):
    """Takes in a genome path (on Negishi) and runs the margie pipeline"""
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "phase": "Initializing",
        "genome_path": genome_data.genome_path,
        "sub_jobs": [],
        "slurm_jobs": [],
        "containers": [],
        "work_dir": None,
        "start_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    command = f"uvx --from ~/bioinformatics-tools/ --force-reinstall dane_wf margie input: {genome_data.genome_path}"
    executor.submit(run_ssh_task, job_id, command)

    return {"success": True, "job_id": job_id, "message": "Job submitted successfully"}


@router.get("/job_status/{job_id}")
async def get_job_status(job_id: str):
    """Get status of a running job"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


@router.get("/job_files/{job_id}")
async def get_job_files(job_id: str, subdir: str = ""):
    """List output files for a completed job via SFTP."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    work_dir = jobs[job_id].get("work_dir")
    if not work_dir:
        raise HTTPException(status_code=400, detail="No working directory available for this job")

    # Validate subdir: no absolute paths, no traversal
    if subdir and (subdir.startswith("/") or ".." in subdir.split("/")):
        raise HTTPException(status_code=400, detail="Invalid subdirectory path")

    target_dir = f"{work_dir}/{subdir}".rstrip("/") if subdir else work_dir

    try:
        entries = ssh_slurm.list_remote_dir(target_dir)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Directory not found on remote")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list remote directory: {str(e)}")

    return {"work_dir": work_dir, "subdir": subdir, "entries": entries}


@router.get("/download_file/{job_id}")
async def download_file(job_id: str, path: str):
    """Download a file from a job's working directory via SFTP."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    work_dir = jobs[job_id].get("work_dir")
    if not work_dir:
        raise HTTPException(status_code=400, detail="No working directory available for this job")

    # Security: reject absolute paths and traversal
    if path.startswith("/") or ".." in path.split("/"):
        raise HTTPException(status_code=400, detail="Invalid file path")

    remote_path = f"{work_dir}/{path}"
    filename = path.split("/")[-1]

    try:
        return StreamingResponse(
            ssh_slurm.stream_remote_file(remote_path),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found on remote")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")


async def job_status_generator(job_id: str):
    """Generator that yields SSE events with job status updates"""
    last_state = None
    last_update_time = 0
    start_time = asyncio.get_event_loop().time()

    while True:
        try:
            # Check job status
            status = ssh_slurm.check_slurm_job_status(job_id)
            print(f'Status: {status}')
            current_state = status['state']
            elapsed = status['elapsed_time']

            # Calculate how long we've been checking
            current_time = asyncio.get_event_loop().time()
            check_duration = int(asyncio.get_event_loop().time() - start_time)

            # Send update if state changed OR it's been 5 seconds since last update
            should_send = (
                current_state != last_state or
                (current_time - last_update_time) >= 7
            )
            print(f'Should send: {should_send} --> current time: {current_time} last update: {last_update_time}')

            if should_send:
                message = f"Job {current_state.lower()} (elapsed: {elapsed}, checking for: {check_duration}s)"
                data = {'state': current_state, 'elapsed': elapsed, 'message': message}
                yield f"data: {json.dumps(data)}\n\n"
                last_state = current_state
                last_update_time = current_time

            # Stop streaming if job is done
            if current_state in ['COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'NOT_FOUND']:
                data = {'state': current_state, 'elapsed': elapsed, 'done': True}
                yield f"data: {json.dumps(data)}\n\n"
                break

            # Wait before checking again
            await asyncio.sleep(10)

        except Exception as e:
            LOGGER.exception("Error checking job status")
            data = {'error': f'Error checking status: {str(e)}'}
            yield f"data: {json.dumps(data)}\n\n"
            break


@router.get("/job_status/{job_id}/stream")
async def stream_job_status(job_id: str):
    """SSE endpoint that streams real-time job status updates"""
    return StreamingResponse(
        job_status_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/all_genomes")
async def all_genomes(path: str):
    print(f'Getting genomes from the path: {path}')
    genomes = ssh_slurm.get_genomes(path)
    return {"success": True, "Genomes": genomes}
