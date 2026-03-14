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

from dataclasses import asdict

from bioinformatics_tools.api.auth import decrypt_private_key, get_current_user
from bioinformatics_tools.api.models import GenomeSend, SlurmSend
from bioinformatics_tools.api.services import job_runner
from bioinformatics_tools.api.services.job_store import job_store
from bioinformatics_tools.utilities import ssh_sftp, ssh_slurm
from bioinformatics_tools.utilities.ssh_connection import make_user_connection
from bioinformatics_tools.workflow_tools.workflow_registry import WORKFLOWS, REQUIRED_SYSTEM_PARAMS

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/ssh", tags=["ssh"])

# Workflows visible on the frontend but not yet implemented.
STUB_WORKFLOWS: set[str] = {"custom_microbiome"}


def _get_available_workflows() -> list[dict]:
    """
    Build the list of available workflows from WORKFLOWS registry.
    Returns detailed metadata for each workflow including tools, params, etc.
    Automatically merges REQUIRED_SYSTEM_PARAMS with workflow-specific params.
    """
    workflows = []

    # Add workflows from WORKFLOWS registry
    for wf_id, wf_key in WORKFLOWS.items():
        # Skip internal test workflows
        if wf_id in ['example', 'selftest']:
            continue

        # Convert dataclass to dict and add computed fields
        wf_dict = asdict(wf_key)
        wf_dict['id'] = wf_key.cmd_identifier
        wf_dict['containers'] = [{'name': sif[0], 'version': sif[1]} for sif in wf_key.sif_files]

        # Merge system-wide required params with workflow-specific params
        # System params come first since they're infrastructure-level
        wf_dict['configurable_params'] = REQUIRED_SYSTEM_PARAMS + (wf_key.configurable_params or [])

        workflows.append(wf_dict)

    # Add stub workflows (not yet implemented but visible)
    # Even stub workflows get system params since they'll need them when implemented
    workflows.append({
        'id': 'custom_microbiome',
        'label': 'Custom Microbiome',
        'description': 'Custom microbiome annotation workflow (coming soon)',
        'full_description': 'A specialized workflow for microbiome annotation. This workflow is currently under development.',
        'tools': [],
        'configurable_params': REQUIRED_SYSTEM_PARAMS,  # Stub still needs system params
        'database_deps': [],
        'docs_url': None,
        'containers': [],
        'cmd_identifier': 'custom_microbiome',
        'snakemake_file': '',
        'other': [],
        'sif_files': [],
    })

    return workflows


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
    """Return the list of user-facing workflows with detailed metadata."""
    return _get_available_workflows()


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


@router.post("/config/create-default")
async def create_default_config(current_user: dict = Depends(get_current_user)):
    """Create a default config file with all system defaults populated."""
    conn = _build_connection(current_user)
    path = _config_path(current_user["home_dir"])

    # Build default config from REQUIRED_SYSTEM_PARAMS
    default_config = {
        "main_database": "~/.local/share/bioinformatics-tools/my-db.db",
        "compute": {
            "cluster-default": {}
        }
    }

    # Populate compute.cluster-default with all defaults from REQUIRED_SYSTEM_PARAMS
    for param in REQUIRED_SYSTEM_PARAMS:
        if param['param'].startswith('compute.cluster-default.'):
            key = param['param'].split('.')[-1]  # Extract the last part (e.g., 'account', 'partition')
            default_value = param.get('default')
            # Use empty string for required fields with no default, otherwise use the default
            default_config['compute']['cluster-default'][key] = default_value if default_value is not None else ""

    try:
        ssh_sftp.write_remote_yaml(path, default_config, connection=conn)
        LOGGER.info("Created default config for user %s at %s", current_user["username"], path)
        return {"success": True, "config": default_config}
    except Exception as exc:
        LOGGER.error("Failed to create default config for %s: %s", current_user["username"], exc)
        raise HTTPException(status_code=500, detail=f"Failed to create default config: {exc}")


@router.post("/test-path-writable")
async def test_path_writable(path_data: dict, current_user: dict = Depends(get_current_user)):
    """Test if a path on the cluster is writable by attempting to create parent directories and a test file."""
    conn = _build_connection(current_user)
    test_path = path_data.get("path", "").strip()

    if not test_path:
        raise HTTPException(status_code=400, detail="Path is required")

    try:
        ssh = conn.connect()

        # Expand ~ to actual home directory
        if test_path.startswith("~"):
            test_path = test_path.replace("~", current_user["home_dir"], 1)

        # Get the directory (remove filename if present)
        import posixpath
        test_dir = posixpath.dirname(test_path)

        # Try to create the directory structure
        _, stdout, stderr = ssh.exec_command(f'mkdir -p "{test_dir}" 2>&1 && echo "DIR_OK"')
        output = stdout.read().decode().strip()

        if "DIR_OK" not in output:
            ssh.close()
            return {
                "writable": False,
                "error": f"Cannot create directory: {test_dir}",
                "details": output
            }

        # Try to write a test file
        test_file = f"{test_path}.write_test"
        _, stdout, stderr = ssh.exec_command(f'touch "{test_file}" 2>&1 && rm -f "{test_file}" 2>&1 && echo "WRITE_OK"')
        output = stdout.read().decode().strip()

        ssh.close()

        if "WRITE_OK" in output:
            return {"writable": True}
        else:
            return {
                "writable": False,
                "error": f"Path is not writable: {test_path}",
                "details": output
            }

    except Exception as exc:
        LOGGER.error("Failed to test path writability for %s: %s", current_user["username"], exc)
        return {
            "writable": False,
            "error": f"Failed to test path: {str(exc)}"
        }


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
    """Submit a genome analysis workflow by name."""
    available_workflows = _get_available_workflows()
    allowed_ids = {wf["id"] for wf in available_workflows}

    if genome_data.workflow not in allowed_ids:
        raise HTTPException(status_code=400, detail=f"Unknown workflow '{genome_data.workflow}'. Available: {sorted(allowed_ids)}")

    if genome_data.workflow in STUB_WORKFLOWS:
        raise HTTPException(status_code=501, detail=f"Workflow '{genome_data.workflow}' is not yet implemented. Check back soon!")

    conn = _build_connection(current_user)

    # Pre-flight: validate required config values are set
    config_path = _config_path(current_user["home_dir"])
    try:
        user_config = ssh_sftp.read_remote_yaml(config_path, connection=conn)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Configuration file not found. Please create a configuration in your Profile settings first."
        )

    # Validate required fields
    missing_fields = []

    # Check main_database
    main_db = user_config.get('main_database')
    if not main_db or str(main_db).strip() == '':
        missing_fields.append('main_database')

    # Check compute.cluster-default.account
    account = user_config.get('compute', {}).get('cluster-default', {}).get('account')
    if not account or str(account).strip() == '':
        missing_fields.append('compute.cluster-default.account (SLURM account)')

    if missing_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Required configuration missing: {', '.join(missing_fields)}. "
                   "Please configure these in your Profile settings before running workflows."
        )

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
        f"echo 'Installing bioinformatics-tools repository...' && "
        f"UV_NO_PROGRESS=1 NO_COLOR=1 uvx --from ~/bioinformatics-tools/ --force-reinstall --quiet"
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


@router.post("/cancel_job/{job_id}")
async def cancel_job(job_id: str, current_user: dict = Depends(get_current_user)):
    """Emergency stop - cancel all SLURM jobs, kill remote process, and mark job as cancelled."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    conn = _build_connection(current_user)

    # Cancel all SLURM subjobs
    slurm_ids = [sj["job_id"] for sj in job_store.get_slurm_jobs(job_id)]
    if slurm_ids:
        ssh_slurm.cancel_slurm_jobs(slurm_ids, connection=conn)
        LOGGER.info("Cancelled %d SLURM jobs for job %s", len(slurm_ids), job_id)

    # Kill the remote dane_wf process on the login node
    # This ensures the SSH task stops immediately instead of waiting for Snakemake to notice
    ssh_slurm.kill_remote_process("dane_wf", connection=conn)
    LOGGER.info("Killed remote dane_wf process for job %s", job_id)

    # Mark job as cancelled (this will also stop the status checker daemon)
    job_store.cancel(job_id)

    return {
        "success": True,
        "message": f"Cancelled job {job_id}",
        "slurm_jobs_cancelled": len(slurm_ids)
    }


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
