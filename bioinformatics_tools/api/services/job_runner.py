"""
Job execution and monitoring.

Contains the core SSH task runner that streams remote output, parses logs
for SLURM job IDs, Snakemake progress, and container metadata, and the
SLURM status checker daemon thread.

The `connection` parameter threads a per-user SSHConnection through from the
API router all the way to the SLURM status checker daemon, so every SSH call
hits the correct cluster and account.
"""
import asyncio
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from bioinformatics_tools.utilities import ssh_slurm
from bioinformatics_tools.utilities.ssh_connection import SSHConnection
from bioinformatics_tools.api.services.job_store import job_store

LOGGER = logging.getLogger(__name__)

# Thread pool for background SSH tasks
executor = ThreadPoolExecutor(max_workers=4)

# Regex patterns for parsing Snakemake/SLURM log output
SLURM_SUBMIT_RE = re.compile(r'SLURM jobid (\d+) \(log:.*?/slurm_logs/(?:rule_|group_[^_]+_)(\w+)/')
SLURM_SUBMIT_FALLBACK_RE = re.compile(r'SLURM jobid (\d+)')
STEPS_PROGRESS_RE = re.compile(r'(\d+) of (\d+) steps \((\d+)%\) done')
CACHE_HIT_RE = re.compile(r'Cache HIT for (\w+)')


def _slurm_status_checker(job_id: str, connection: SSHConnection):
    """Daemon thread that periodically checks SLURM job statuses."""
    while job_store.get_status(job_id) == "running":
        slurm_jobs = job_store.get_slurm_jobs(job_id)
        active_ids = [sj["job_id"] for sj in slurm_jobs if sj["status"] not in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "CACHED")]
        if active_ids:
            try:
                statuses = ssh_slurm.check_multiple_slurm_jobs(active_ids, connection=connection)
                for sj in slurm_jobs:
                    if sj["job_id"] in statuses:
                        sj["status"] = statuses[sj["job_id"]]["state"]
                        sj["time"] = statuses[sj["job_id"]]["time"]
            except Exception as e:
                LOGGER.warning("SLURM status check failed: %s", e)
        # Wait 15 seconds between checks
        for _ in range(15):
            if job_store.get_status(job_id) != "running":
                break
            time.sleep(1)


def run_ssh_task(job_id: str, command: str, connection: SSHConnection):
    """Generic SSH task runner with log parsing, SLURM tracking, and progress parsing."""
    job_store.update(job_id, status="running", phase="Submitting via SSH", logs="")

    # Start SLURM status checker daemon thread (passes the same connection through)
    checker = threading.Thread(
        target=_slurm_status_checker,
        args=(job_id, connection),
        daemon=True
    )
    checker.start()

    try:
        for line in ssh_slurm.submit_ssh_job(cmd=command, connection=connection):
            # Detect work_dir metadata from submit_ssh_job
            if line.startswith("__WORKDIR__:"):
                job_store.update(job_id, work_dir=line.split(":", 1)[1])
                continue

            # Parse container metadata from bapptainer log lines
            if "__CONTAINER__:" in line:
                try:
                    container_json = line.split("__CONTAINER__:", 1)[1]
                    job_store.add_container(job_id, json.loads(container_json))
                except (json.JSONDecodeError, IndexError):
                    pass

            job_store.append_log(job_id, line)

            # Parse cache-restored rules (from output_cache.py "Cache HIT for <tool>")
            cache_match = CACHE_HIT_RE.search(line)
            if cache_match:
                rule_name = cache_match.group(1)
                job_store.add_slurm_job(job_id, "—", rule_name)
                # Immediately mark as CACHED so the checker skips it
                for sj in job_store.get_slurm_jobs(job_id):
                    if sj["rule"] == rule_name and sj["job_id"] == "—":
                        sj["status"] = "CACHED"

            # Parse SLURM job IDs as they appear in the log stream
            match = SLURM_SUBMIT_RE.search(line)
            if match:
                slurm_id, rule_name = match.groups()
                job_store.add_slurm_job(job_id, slurm_id, rule_name)
            elif SLURM_SUBMIT_FALLBACK_RE.search(line):
                fallback = SLURM_SUBMIT_FALLBACK_RE.search(line)
                slurm_id = fallback.group(1)
                job_store.add_slurm_job(job_id, slurm_id, "unknown")

            # Parse Snakemake step progress (e.g. "2 of 4 steps (50%) done")
            progress_match = STEPS_PROGRESS_RE.search(line)
            if progress_match:
                done, total, pct = progress_match.groups()
                job_store.update(job_id, steps_done=int(done), steps_total=int(total), progress=int(pct))

            # Update phase based on output
            if "snakemake" in line.lower():
                job_store.update(job_id, phase="Running Snakemake")

        job_store.update(job_id, status="completed", phase="Done")
    except Exception as e:
        job_store.update(job_id, status="failed")
        job_store.append_log(job_id, f"\nError: {str(e)}")


def submit_job(job_id: str, command: str, connection: SSHConnection):
    """Submit a job to the thread pool executor."""
    executor.submit(run_ssh_task, job_id, command, connection)


async def job_status_generator(job_id: str):
    """Generator that yields SSE events with job status updates."""
    last_state = None
    last_update_time = 0
    start_time = asyncio.get_event_loop().time()

    while True:
        try:
            status = ssh_slurm.check_slurm_job_status(job_id)
            current_state = status['state']
            elapsed = status['elapsed_time']

            current_time = asyncio.get_event_loop().time()
            check_duration = int(current_time - start_time)

            should_send = (
                current_state != last_state or
                (current_time - last_update_time) >= 7
            )

            if should_send:
                message = f"Job {current_state.lower()} (elapsed: {elapsed}, checking for: {check_duration}s)"
                data = {'state': current_state, 'elapsed': elapsed, 'message': message}
                yield f"data: {json.dumps(data)}\n\n"
                last_state = current_state
                last_update_time = current_time

            if current_state in ['COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'NOT_FOUND']:
                data = {'state': current_state, 'elapsed': elapsed, 'done': True}
                yield f"data: {json.dumps(data)}\n\n"
                break

            await asyncio.sleep(10)

        except Exception as e:
            LOGGER.exception("Error checking job status")
            data = {'error': f'Error checking status: {str(e)}'}
            yield f"data: {json.dumps(data)}\n\n"
            break
