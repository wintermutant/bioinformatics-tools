'''
This is essentially a linker module that uses ssh to run $ dane commands
This allows the CLI to be ported and ran through SSH to interface with HPCs,
centering around running login node and SLURM commands. Since we use Snakemake,
which controls SLURM batching and queueing, we can mainly run on login node.
'''
from datetime import datetime
import logging

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
    Yields each line as it arrives from the remote process.
    '''
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('negishi.rcac.purdue.edu', username='ddeemer')
    LOGGER.info('Connected!')

    timestamp = datetime.now().strftime('%Y-%m-%d-%H%M')
    work_dir = f'/depot/lindems/data/margie/tests/{timestamp}'
    LOGGER.info('Running in working directory: %s', work_dir)
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
