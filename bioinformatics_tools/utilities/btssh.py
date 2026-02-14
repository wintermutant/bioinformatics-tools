import uuid
from pathlib import Path
import paramiko
import asyncio
import re
from typing import Optional, Callable


class AsyncSLURMJob:
    default_job_dir: str = "~/.bioinformatics-tools"

    def __init__(self, host='negishi.rcac.purdue.edu', username='ddeemer', config=None):
        self.host = host
        self.username = username
        self.ssh: paramiko.SSHClient | None = None
        self.config = config
        #TODO: Allow a config file and then parse it
        job_id = uuid.uuid4().hex[:8]  # Short UUID
        self.job_location = f"{self.default_job_dir}/job-{job_id}.sh"

    def connect(self):
        """Establish SSH connection"""
        if not self.ssh:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            print(f'Connecting to {self.host}...')
            self.ssh.connect(self.host, username=self.username)
            print('Connected!')

    def submit_job(self, script_content: str, nodes=1, cpus=4, mem='4G', time='00:30:00') -> str:
        """Submit SLURM job and return job ID"""
        if not self.ssh:
            self.connect()

        # Create SLURM script
        slurm_script = f"""#!/bin/bash
#SBATCH -A lindems
#SBATCH --partition=cpu
#SBATCH --nodes={nodes}
#SBATCH --cpus-per-task={cpus}
#SBATCH --mem={mem}
#SBATCH --time={time}
#SBATCH --job-name=remote_job

{script_content}
"""

        # Write script and submit
        stdin, stdout, stderr = self.ssh.exec_command(
            f'cat > {self.job_location} << "EOF"\n{slurm_script}\nEOF\n'
            f'sbatch {self.job_location}'
        )

        result = stdout.read().decode().strip()
        error = stderr.read().decode().strip()

        if error:
            print(f"Error submitting job: {error}")
            return None

        # Extract job ID from sbatch output (e.g., "Submitted batch job 12345")
        match = re.search(r'(\d+)', result)
        if match:
            job_id = match.group(1)
            print(f"Submitted job {job_id}")
            return job_id
        else:
            print(f"Could not parse job ID from: {result}")
            return None

    def check_job_status(self, job_id: str) -> Optional[str]:
        """
        Check if job is still in queue
        Returns: 'PENDING', 'RUNNING', 'COMPLETED', or None if not found
        """
        if not self.ssh:
            self.connect()

        stdin, stdout, stderr = self.ssh.exec_command(f'squeue -j {job_id} -o "%T"')
        output = stdout.read().decode().strip()

        # squeue returns header + status, or just header if job is done
        lines = output.split('\n')
        if len(lines) > 1:
            status = lines[1].strip()
            return status
        else:
            # Job not in queue = completed (or failed)
            return 'COMPLETED'

    async def monitor_job(self, job_id: str, poll_interval: int = 5,
                         on_status_change: Optional[Callable] = None) -> str:
        """
        Async monitoring of SLURM job

        Returns:
            Final status of the job
        """
        last_status = None

        while True:
            # Run blocking SSH call in executor to not block event loop
            status = await asyncio.to_thread(self.check_job_status, job_id)

            if status != last_status:
                print(f"[Job {job_id}] Status: {status}")
                if on_status_change:
                    on_status_change(status)
                last_status = status

            if status == 'COMPLETED':
                print(f"[Job {job_id}] Finished!")
                return status

            # Wait before next check
            await asyncio.sleep(poll_interval)

    def get_job_output(self, job_id: str) -> str:
        """Fetch the output file from completed job"""
        if not self.ssh:
            self.connect()

        # Default SLURM output file name
        stdin, stdout, stderr = self.ssh.exec_command(f'cat slurm-{job_id}.out')
        return stdout.read().decode()

    def close(self):
        """Close SSH connection"""
        if self.ssh:
            self.ssh.close()
            print("SSH connection closed")
