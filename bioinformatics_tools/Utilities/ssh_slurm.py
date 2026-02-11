'''
This is essentially a linker module that uses ssh to run $ dane commands
This allows the CLI to be ported and ran through SSH to interface with HPCs,
centering around running login node and SLURM commands. Since we use Snakemake,
which controls SLURM batching and queueing, we can mainly run on login node.
'''
from datetime import datetime
import logging
import stat

import paramiko

LOGGER = logging.getLogger(__name__)

def get_genomes(location):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print('Waiting to connect...')
    ssh.connect('negishi.rcac.purdue.edu', username='ddeemer')
    print(f'Connected!\nls -lah {location}')
    stdin, stdout, stderr = ssh.exec_command(f'ls -lah {location}')
    output = stdout.read().decode()
    error = stderr.read().decode()
    ssh.close()

    if error:
        print(f'Error: {error}')

    # Split output into lines and filter out empty lines
    files = [line.strip() for line in output.split('\n') if line.strip()]
    print(f'Found files...\n{files}')
    return files


def submit_ssh_job(cmd):
    '''Generator that streams remote output line-by-line via SSH.
    Yields a __WORKDIR__: metadata line first, then each output line as it arrives.
    '''
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('negishi.rcac.purdue.edu', username='ddeemer')
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
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f'Waiting to connect...')
    ssh.connect('negishi.rcac.purdue.edu', username='ddeemer')
    print(f'Connected!')

    stdin, stdout, stderr = ssh.exec_command('touch im-here.flag')
    # stdin, stdout, stderr = ssh.exec_command('touch ~/myfile2.txt')

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
        stdin_content = stdin.read().decode().strip()
    except OSError:
        stdin_content = 'None'
    try:
        stderr_content = stderr.read().decode().strip()
    except OSError:
        stderr_content = 'None'
    print(f'Inside of submit_slurm_job:\nstdin: {stdin_content}\nstdout: {job_id},\nstderr: {stderr_content}\n')
    ssh.close()
    # Extract just the job number (sbatch returns "Submitted batch job 12345")
    if "Submitted batch job" in job_id:
        job_id = job_id.split()[-1]
    return job_id


def check_slurm_job_status(job_id):
    """
    Check the status of a SLURM job
    Returns: dict with status info (state, elapsed_time, etc.)
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('negishi.rcac.purdue.edu', username='ddeemer')

    # Use squeue to check if job is running/~pending
    stdin, stdout, stderr = ssh.exec_command(f'squeue -j {job_id} --format="%T %M %j %a %l" --noheader')
    squeue_output = stdout.read().decode().strip()

    if squeue_output:
        # Job is still in queue (PENDING or RUNNING)
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

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('negishi.rcac.purdue.edu', username='ddeemer')

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


def list_remote_dir(remote_path: str) -> list[dict]:
    """List files and directories in a remote path via SFTP.

    Returns a list of dicts: {name, type, size}.
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('negishi.rcac.purdue.edu', username='ddeemer')

    sftp = ssh.open_sftp()
    entries = []
    for attr in sftp.listdir_attr(remote_path):
        entry_type = 'directory' if stat.S_ISDIR(attr.st_mode) else 'file'
        entries.append({
            'name': attr.filename,
            'type': entry_type,
            'size': attr.st_size,
        })

    sftp.close()
    ssh.close()
    return entries


def stream_remote_file(remote_path: str):
    """Generator that streams a remote file in chunks via SFTP.

    Yields bytes chunks (8KB each).
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('negishi.rcac.purdue.edu', username='ddeemer')

    sftp = ssh.open_sftp()
    with sftp.open(remote_path, 'rb') as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            yield chunk

    sftp.close()
    ssh.close()
