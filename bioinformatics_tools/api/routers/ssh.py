"""
Fasta file processing endpoints
"""
import asyncio
import json
import logging
import os
import datetime
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

def run_margie_task(job_id: str, genome_path: str):
    '''Runs in a thread pool worker'''
    jobs[job_id]["status"] = "running"
    jobs[job_id]["phase"] = "Submitting to (Negishi (SSH)"
    jobs[job_id]["logs"] = ""
    try:
        command = f"uvx --from ~/bioinformatics-tools/ --force-reinstall dane_wf margie input: {genome_path}"
        # submit_ssh_job is a generator - consume it and collect output
        for line in ssh_slurm.submit_ssh_job(cmd=command):
            jobs[job_id]["logs"] += line + "\n"
            # Update phase based on output if needed
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
        "start_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    # Submit to thread pool - returns immediately
    executor.submit(run_margie_task, job_id, genome_data.genome_path)

    return {"success": True, "job_id": job_id, "message": "Job submitted successfully"}


@router.get("/job_status/{job_id}")
async def get_job_status(job_id: str):
    """Get status of a running job"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


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
