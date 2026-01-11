"""
Fasta file processing endpoints
"""
import asyncio
import json
import logging
import os

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pymongo import MongoClient

from bioinformatics_tools.api.models import GenericRequest, GenericResponse
from bioinformatics_tools.utilities import ssh_slurm

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/example", tags=["example"])


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

@router.post("/run_slurm")
async def run_slurm(content: SlurmSend):
    """Submit a SLURM job and return the job ID immediately"""
    job_id = ssh_slurm.submit_slurm_job(script_content=content.script)
    print(f'Inside of run_slurm, job id: {job_id}')
    return {"success": True, "job_id": job_id, "message": "Job submitted successfully"}


@router.post("/run_ssh")
async def run_shh(content: SlurmSend):
    """Submit a SLURM job and return the job ID immediately"""
    std_txt = ssh_slurm.submit_ssh_job(cmd=content.script)
    print(f'Inside of run_shh. std_txt:\n{std_txt}')
    return {"success": True, "std_txt": std_txt, "message": "Job submitted successfully"}


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
