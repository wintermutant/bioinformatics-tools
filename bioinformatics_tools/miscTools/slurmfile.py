import typer
from pathlib import Path
from typing import Optional
from datetime import datetime

app = typer.Typer()

@app.command()
def main(
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output SLURM script filename"),
    job_name: str = typer.Option("my_job", "--job-name", "-j", help="Job name"),
    partition: Optional[str] = typer.Option(None, "--partition", "-p", help="SLURM partition/queue"),
    time: str = typer.Option("01:00:00", "--time", "-t", help="Job time limit (HH:MM:SS)"),
    nodes: int = typer.Option(1, "--nodes", "-n", help="Number of nodes"),
    cpus: int = typer.Option(1, "--cpus", "-c", help="Number of CPUs per task"),
    memory: str = typer.Option("4G", "--memory", "-m", help="Memory per node (e.g., 4G, 1000M)"),
    email: Optional[str] = typer.Option(None, "--email", "-e", help="Email address for notifications")
):
    """
    Generate a SLURM batch script skeleton with common options.

    Creates a well-structured SLURM script template with customizable parameters
    and helpful comments for common options.
    """

    # Generate default filename with timestamp if not provided
    if output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = Path(f"job-{timestamp}.slurm")

    # Build the SLURM script content
    script_content = f"""#!/bin/bash

#SBATCH --job-name={job_name}
#SBATCH --output={job_name}_%j.out
#SBATCH --error={job_name}_%j.err
#SBATCH --time={time}
#SBATCH --nodes={nodes}
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task={cpus}
#SBATCH --mem={memory}
"""

    # Add partition if specified
    if partition:
        script_content += f"#SBATCH --partition={partition}\n"

    # Add email notifications if specified
    if email:
        script_content += f"""#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --mail-user={email}
"""

    # Add commonly used but commented options
    script_content += """
# Uncomment and modify the following options as needed:
# #SBATCH --array=1-10                    # Job array (1-10)
# #SBATCH --dependency=afterok:12345      # Job dependency
# #SBATCH --exclusive                     # Exclusive node access
# #SBATCH --gres=gpu:1                    # GPU resources
# #SBATCH --constraint=intel              # Node constraints
# #SBATCH --account=myaccount             # Account to charge
# #SBATCH --qos=normal                    # Quality of service
# #SBATCH --workdir=/path/to/workdir      # Working directory


# Set up environment variables
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

# Your commands here
echo "Starting job..."

echo "Job completed at: $(date)"
"""

    # Write the script to file
    try:
        with open(output, 'w') as f:
            f.write(script_content)

        # Make the script executable
        output.chmod(0o755)

        print(f"✅ SLURM script created: {output}")
        print(f"📝 Job name: {job_name}")
        print(f"⏱️  Time limit: {time}")
        print(f"💻 Resources: {nodes} node(s), {cpus} CPU(s), {memory} memory")
        if partition:
            print(f"🎯 Partition: {partition}")
        if email:
            print(f"📧 Email notifications: {email}")
        print(f"\n🚀 Submit with: sbatch {output}")

    except Exception as e:
        print(f"❌ Error creating SLURM script: {e}")
        raise typer.Exit(code=1)
