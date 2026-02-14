'''
SSH-based SLURM operations for interfacing with HPC clusters.

Uses paramiko to run login node and SLURM commands. Since we use Snakemake,
which controls SLURM batching and queueing, we can mainly run on login node.
'''
from datetime import datetime
import logging

from bioinformatics_tools.utilities.ssh_connection import default_connection

LOGGER = logging.getLogger(__name__)


def get_genomes(location):
    """List genome files at a remote path via SSH ls."""
    ssh = default_connection.connect()
    LOGGER.info('ls -lah %s', location)
    stdin, stdout, stderr = ssh.exec_command(f'ls -lah {location}')
    output = stdout.read().decode()
    error = stderr.read().decode()
    ssh.close()

    if error:
        LOGGER.warning('Error listing genomes: %s', error)

    files = [line.strip() for line in output.split('\n') if line.strip()]
    return files


def submit_ssh_job(cmd):
    '''Generator that streams remote output line-by-line via SSH.
    Yields a __WORKDIR__: metadata line first, then each output line as it arrives.
    '''
    ssh = default_connection.connect()
    LOGGER.info('Connected!')

    timestamp = datetime.now().strftime('%Y-%m-%d-%H%M')
    work_dir = f'/depot/lindems/data/margie/tests/{timestamp}'
    LOGGER.info('Running in working directory: %s', work_dir)

    # Yield the working directory as metadata for the caller
    yield f'__WORKDIR__:{work_dir}'

    wrapped_cmd = f'export PATH=$HOME/.local/bin:$PATH && mkdir -p {work_dir} && cd {work_dir} && {cmd} 2>&1'  #TODO: I really don't like this, but points to uv/uvx

    # ---------------------- Meat and potatoes of execution ---------------------- #
    stdin, stdout, stderr = ssh.exec_command(wrapped_cmd, get_pty=True)

    for line in iter(stdout.readline, ''):
        LOGGER.info('[remote] %s', line.rstrip())
        yield line.rstrip()

    LOGGER.info('Remote execution completed.')
    ssh.close()


def submit_slurm_job(script_content, nodes=1, cpus=4, mem='4G', time='00:30:00'):
    """Write a SLURM batch script and submit it via sbatch."""
    ssh = default_connection.connect()

    stdin, stdout, stderr = ssh.exec_command('touch im-here.flag')

    # Create SLURM script
    slurm_script = f"""#!/bin/bash
#SBATCH -A lindems
#SBATCH --partition=cpu
#SBATCH --nodes={nodes}
#SBATCH --cpus-per-task={cpus}
#SBATCH --mem={mem}
#SBATCH --time={time}
#SBATCH --job-name=remote_job

# TODO: Here, we need script_content

source /etc/profile

{script_content}
    """
    # Write script and submit
    stdin, stdout, stderr = ssh.exec_command(
        f'cat > ~/job.sh << "EOF"\n{slurm_script}\nEOF\n'
        f'sbatch ~/job.sh'
    )

    job_id = stdout.read().decode().strip()
    try:
        stderr_content = stderr.read().decode().strip()
    except OSError:
        stderr_content = 'None'

    LOGGER.info('submit_slurm_job stdout: %s, stderr: %s', job_id, stderr_content)
    ssh.close()

    # Extract just the job number (sbatch returns "Submitted batch job 12345")
    if "Submitted batch job" in job_id:
        job_id = job_id.split()[-1]
    return job_id


def check_slurm_job_status(job_id):
    """Check the status of a single SLURM job via squeue then sacct.

    Returns: dict with status info (state, elapsed_time, etc.)
    """
    ssh = default_connection.connect()

    # Use squeue to check if job is running/pending
    stdin, stdout, stderr = ssh.exec_command(f'squeue -j {job_id} --format="%T %M %j %a %l" --noheader')
    squeue_output = stdout.read().decode().strip()

    if squeue_output:
        parts = squeue_output.split()
        state = parts[0] if len(parts) > 0 else "UNKNOWN"
        elapsed = parts[1] if len(parts) > 1 else "0:00"
        job_name = parts[2] if len(parts) > 2 else "0:00"
        account = parts[3] if len(parts) > 3 else "0:00"
        limit = parts[4] if len(parts) > 4 else "0:00"
        ssh.close()
        return {"state": state, "elapsed_time": elapsed, "job_name": job_name, "account": account, "time limit": limit, "exists": True}

    # Job not in queue, check sacct for completed/failed jobs
    stdin, stdout, stderr = ssh.exec_command(f'sacct -j {job_id} --format=JobName,State,Elapsed --noheader | head -1')
    sacct_output = stdout.read().decode().strip()

    ssh.close()

    if sacct_output:
        parts = sacct_output.split()
        job_name = parts[0] if len(parts) > 0 else "UNKNOWN"
        state = parts[1] if len(parts) > 1 else "UNKNOWN"
        elapsed = parts[2] if len(parts) > 2 else "0:00"
        return {"job_name": job_name, "state": state, "elapsed_time": elapsed, "exists": True}

    return {"state": "NOT_FOUND", "elapsed_time": "0:00", "exists": False}


def check_multiple_slurm_jobs(job_ids: list[str]) -> dict[str, dict]:
    """Check status of multiple SLURM jobs in a single SSH call.

    Returns a dict mapping each job_id to {"state": ..., "time": ...}.
    """
    if not job_ids:
        return {}

    ssh = default_connection.connect()

    results = {}
    ids_str = ",".join(job_ids)

    # Try squeue first for active jobs
    stdin, stdout, stderr = ssh.exec_command(
        f'squeue -j {ids_str} --format="%i %T %M" --noheader 2>/dev/null'
    )
    squeue_output = stdout.read().decode().strip()

    found_ids = set()
    if squeue_output:
        for line in squeue_output.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                jid, state, elapsed = parts[0], parts[1], parts[2]
                results[jid] = {"state": state, "time": elapsed}
                found_ids.add(jid)

    # For any IDs not found in squeue, check sacct
    missing = [jid for jid in job_ids if jid not in found_ids]
    if missing:
        missing_str = ",".join(missing)
        stdin, stdout, stderr = ssh.exec_command(
            f'sacct -j {missing_str} --format=JobID,State,Elapsed --noheader --parsable2 2>/dev/null'
        )
        sacct_output = stdout.read().decode().strip()
        if sacct_output:
            for line in sacct_output.splitlines():
                parts = line.split("|")
                if len(parts) >= 3:
                    jid = parts[0].split(".")[0]  # strip .batch/.extern suffix
                    if jid in missing and jid not in results:
                        results[jid] = {"state": parts[1], "time": parts[2]}

    ssh.close()
    return results
