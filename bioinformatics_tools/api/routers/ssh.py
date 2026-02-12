"""
SSH and job management endpoints.

Thin routing layer — delegates to job_store, job_runner, and ssh utilities.
"""
import logging
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from bioinformatics_tools.api.models import SlurmSend, GenomeSend
from bioinformatics_tools.api.services.job_store import job_store
from bioinformatics_tools.api.services import job_runner
from bioinformatics_tools.utilities import ssh_slurm
from bioinformatics_tools.utilities import ssh_sftp

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/ssh", tags=["ssh"])


@router.get("/health")
async def health_check():
    """Test endpoint to verify API is working"""
    return {"status": "success"}


@router.post("/run_slurm")
async def run_slurm(content: SlurmSend):
    """Submit a SLURM job and return the job ID immediately"""
    job_id = ssh_slurm.submit_slurm_job(script_content=content.script)
    return {"success": True, "job_id": job_id, "message": "Job submitted successfully"}


@router.post("/run_ssh")
async def run_ssh(content: SlurmSend):
    """Execute an SSH command and return output"""
    LOGGER.info('Running run_ssh')
    std_txt = ssh_slurm.submit_ssh_job(cmd=content.script)
    return {"success": True, "std_txt": std_txt, "message": "Job submitted successfully"}


@router.post("/run_margie")
async def run_margie(genome_data: GenomeSend):
    """Takes in a genome path (on Negishi) and runs the margie pipeline"""
    job_id = str(uuid.uuid4())
    job_store.create(job_id, genome_data.genome_path)

    command = f"uvx --from ~/bioinformatics-tools/ --force-reinstall dane_wf margie input: {genome_data.genome_path}"
    job_runner.submit_job(job_id, command)

    return {"success": True, "job_id": job_id, "message": "Job submitted successfully"}


@router.get("/job_status/{job_id}")
async def get_job_status(job_id: str):
    """Get status of a running job"""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/job_files/{job_id}")
async def get_job_files(job_id: str, subdir: str = ""):
    """List output files for a job via SFTP."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    work_dir = job.get("work_dir")
    if not work_dir:
        raise HTTPException(status_code=400, detail="No working directory available for this job")

    # Validate subdir: no absolute paths, no traversal
    if subdir and (subdir.startswith("/") or ".." in subdir.split("/")):
        raise HTTPException(status_code=400, detail="Invalid subdirectory path")

    target_dir = f"{work_dir}/{subdir}".rstrip("/") if subdir else work_dir

    try:
        entries = ssh_sftp.list_remote_dir(target_dir)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Directory not found on remote")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list remote directory: {str(e)}")

    return {"work_dir": work_dir, "subdir": subdir, "entries": entries}


@router.get("/download_file/{job_id}")
async def download_file(job_id: str, path: str):
    """Download a file from a job's working directory via SFTP."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    work_dir = job.get("work_dir")
    if not work_dir:
        raise HTTPException(status_code=400, detail="No working directory available for this job")

    # Security: reject absolute paths and traversal
    if path.startswith("/") or ".." in path.split("/"):
        raise HTTPException(status_code=400, detail="Invalid file path")

    remote_path = f"{work_dir}/{path}"
    filename = path.split("/")[-1]

    try:
        return StreamingResponse(
            ssh_sftp.stream_remote_file(remote_path),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found on remote")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")


@router.get("/job_status/{job_id}/stream")
async def stream_job_status(job_id: str):
    """SSE endpoint that streams real-time job status updates"""
    return StreamingResponse(
        job_runner.job_status_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/all_genomes")
async def all_genomes(path: str):
    """List genome files at a remote path"""
    genomes = ssh_slurm.get_genomes(path)
    return {"success": True, "Genomes": genomes}
