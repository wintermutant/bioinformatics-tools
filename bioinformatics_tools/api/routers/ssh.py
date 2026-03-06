"""
SSH and job management endpoints.

Thin routing layer — delegates to job_store, job_runner, and ssh utilities.

All endpoints (except /health) require a valid Bearer token. The token is
validated by get_current_user(), which returns the user's cluster credentials.
_build_connection() decrypts the stored private key and builds a per-user
SSHConnection for each request.
"""
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from bioinformatics_tools.api.auth import decrypt_private_key, get_current_user
from bioinformatics_tools.api.models import GenomeSend, SlurmSend
from bioinformatics_tools.api.services import job_runner
from bioinformatics_tools.api.services.job_store import job_store
from bioinformatics_tools.utilities import ssh_sftp, ssh_slurm
from bioinformatics_tools.utilities.ssh_connection import make_user_connection

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/ssh", tags=["ssh"])

# User-facing workflows available from the analyze page.
# Add new entries here as workflows are added to workflow_keys in workflow.py.
AVAILABLE_WORKFLOWS: list[dict] = [
    {"id": "margie", "label": "Margie", "description": "Full annotation pipeline (Prodigal, Pfam, COG)"},
    {"id": "custom_microbiome", "label": "CustomMicrobiome", "description": "Custom microbiome annotation workflow (coming soon)"},
]

# Workflows visible on the frontend but not yet implemented.
STUB_WORKFLOWS: set[str] = {"custom_microbiome"}


def _build_connection(current_user: dict):
    """Decrypt the user's stored private key and return a ready SSHConnection."""
    private_key = decrypt_private_key(current_user['private_key_encrypted'])
    return make_user_connection(
        current_user['cluster_host'],
        current_user['cluster_username'],
        private_key,
    )


def _config_path(home_dir: str) -> str:
    """Remote path to the user's BSP config file."""
    return f'{home_dir}/.config/bioinformatics-tools/config.yaml'


@router.get("/workflows")
async def list_workflows(current_user: dict = Depends(get_current_user)):
    """Return the list of user-facing workflows available on the analyze page."""
    return AVAILABLE_WORKFLOWS


@router.get("/health")
async def health_check():
    """Test endpoint to verify API is working. No auth required."""
    return {"status": "success"}


@router.get("/status")
async def ssh_status(current_user: dict = Depends(get_current_user)):
    """Check whether the BSP server can reach the user's cluster via SSH."""
    try:
        conn = _build_connection(current_user)
        ssh = conn.connect()
        ssh.close()
        return {"connected": True, "host": current_user["cluster_host"]}
    except Exception as exc:
        LOGGER.warning("SSH status check failed for user %s: %s", current_user["username"], exc)
        return {"connected": False, "host": current_user["cluster_host"]}


@router.get("/config")
async def get_config(current_user: dict = Depends(get_current_user)):
    """Read the user's ~/.config/bioinformatics-tools/config.yaml from their cluster via SFTP."""
    conn = _build_connection(current_user)
    path = _config_path(current_user["home_dir"])
    try:
        data = ssh_sftp.read_remote_yaml(path, connection=conn)
        return data
    except Exception as exc:
        LOGGER.error("Failed to read remote config for %s: %s", current_user["username"], exc)
        raise HTTPException(status_code=500, detail=f"Failed to read remote config: {exc}")


@router.put("/config")
async def save_config(config: dict, current_user: dict = Depends(get_current_user)):
    """Write a config dict back to the user's cluster as YAML via SFTP."""
    conn = _build_connection(current_user)
    path = _config_path(current_user["home_dir"])
    try:
        ssh_sftp.write_remote_yaml(path, config, connection=conn)
        return {"success": True}
    except Exception as exc:
        LOGGER.error("Failed to write remote config for %s: %s", current_user["username"], exc)
        raise HTTPException(status_code=500, detail=f"Failed to write remote config: {exc}")


@router.post("/run_slurm")
async def run_slurm(content: SlurmSend, current_user: dict = Depends(get_current_user)):
    """Submit a SLURM job and return the job ID immediately."""
    conn = _build_connection(current_user)
    job_id = ssh_slurm.submit_slurm_job(script_content=content.script, connection=conn)
    return {"success": True, "job_id": job_id, "message": "Job submitted successfully"}


@router.post("/run_ssh")
async def run_ssh(content: SlurmSend, current_user: dict = Depends(get_current_user)):
    """Execute an SSH command and return output."""
    LOGGER.info('Running run_ssh for user %s', current_user["username"])
    conn = _build_connection(current_user)
    std_txt = ssh_slurm.submit_ssh_job(cmd=content.script, connection=conn)
    return {"success": True, "std_txt": std_txt, "message": "Job submitted successfully"}


@router.post("/run_workflow")
async def run_workflow(genome_data: GenomeSend, current_user: dict = Depends(get_current_user)):
    """Submit a genome analysis workflow by name. Workflow must be in AVAILABLE_WORKFLOWS."""
    allowed_ids = {wf["id"] for wf in AVAILABLE_WORKFLOWS}
    if genome_data.workflow not in allowed_ids:
        raise HTTPException(status_code=400, detail=f"Unknown workflow '{genome_data.workflow}'. Available: {sorted(allowed_ids)}")

    if genome_data.workflow in STUB_WORKFLOWS:
        raise HTTPException(status_code=501, detail=f"Workflow '{genome_data.workflow}' is not yet implemented. Check back soon!")

    conn = _build_connection(current_user)

    # Pre-flight: verify the genome file exists on the cluster before creating a job.
    try:
        ssh_sftp.check_remote_file(genome_data.genome_path, conn)
    except FileNotFoundError:
        raise HTTPException(
            status_code=400,
            detail=f"Genome file not found on the cluster: '{genome_data.genome_path}'. "
                   "Make sure the path is a Negishi path, not a path on your local machine.",
        )
    except IsADirectoryError:
        raise HTTPException(
            status_code=400,
            detail=f"Path points to a directory, not a file: '{genome_data.genome_path}'",
        )
    except Exception as exc:
        LOGGER.warning("File pre-check failed for %s: %s", genome_data.genome_path, exc)
        raise HTTPException(
            status_code=400,
            detail=f"Could not verify genome file on cluster: {exc}",
        )

    job_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime('%Y-%m-%d-%H%M')
    base_dir = (genome_data.output_dir or current_user['home_dir']).rstrip('/')
    output_dir = f"{base_dir}/{timestamp}"

    job_store.create(job_id, genome_data.genome_path, user_id=current_user["user_id"])
    job_store.update(job_id, work_dir=output_dir)

    command = (
        f"uvx --from ~/bioinformatics-tools/ --force-reinstall"
        f" dane_wf {genome_data.workflow} input: {genome_data.genome_path} output_dir: {output_dir}"
    )
    job_runner.submit_job(job_id, command, connection=conn)

    return {"success": True, "job_id": job_id, "output_dir": output_dir, "message": "Job submitted successfully"}


@router.get("/job_status/{job_id}")
async def get_job_status(job_id: str, current_user: dict = Depends(get_current_user)):
    """Get status of a running job. Returns 403 if the job belongs to a different user."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return {**job, "cluster_host": current_user["cluster_host"]}


@router.get("/job_files/{job_id}")
async def get_job_files(
    job_id: str,
    subdir: str = "",
    current_user: dict = Depends(get_current_user),
):
    """List output files for a job via SFTP."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    work_dir = job.get("work_dir")
    if not work_dir:
        raise HTTPException(status_code=400, detail="No working directory available for this job")

    if subdir and (subdir.startswith("/") or ".." in subdir.split("/")):
        raise HTTPException(status_code=400, detail="Invalid subdirectory path")

    target_dir = f"{work_dir}/{subdir}".rstrip("/") if subdir else work_dir
    conn = _build_connection(current_user)

    try:
        entries = ssh_sftp.list_remote_dir(target_dir, connection=conn)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Directory not found on remote")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list remote directory: {str(e)}")

    return {"work_dir": work_dir, "subdir": subdir, "entries": entries}


@router.get("/download_file/{job_id}")
async def download_file(
    job_id: str,
    path: str,
    current_user: dict = Depends(get_current_user),
):
    """Download a file from a job's working directory via SFTP."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    work_dir = job.get("work_dir")
    if not work_dir:
        raise HTTPException(status_code=400, detail="No working directory available for this job")

    if path.startswith("/") or ".." in path.split("/"):
        raise HTTPException(status_code=400, detail="Invalid file path")

    remote_path = f"{work_dir}/{path}"
    filename = path.split("/")[-1]
    conn = _build_connection(current_user)

    try:
        return StreamingResponse(
            ssh_sftp.stream_remote_file(remote_path, connection=conn),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found on remote")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")


@router.get("/job_status/{job_id}/stream")
async def stream_job_status(job_id: str, current_user: dict = Depends(get_current_user)):
    """SSE endpoint that streams real-time job status updates."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    return StreamingResponse(
        job_runner.job_status_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/all_genomes")
async def all_genomes(path: str, current_user: dict = Depends(get_current_user)):
    """List genome files at a remote path on the user's cluster."""
    conn = _build_connection(current_user)
    genomes = ssh_slurm.get_genomes(path, connection=conn)
    return {"success": True, "Genomes": genomes}
