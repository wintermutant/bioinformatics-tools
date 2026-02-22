"""
In-memory job state management.

Provides a JobStore class that wraps the jobs dict with structured
methods for creating, reading, and updating job state. All job state
mutations go through this module.
"""
import datetime
import logging

LOGGER = logging.getLogger(__name__)


class JobStore:
    """In-memory job state management."""

    def __init__(self):
        self._jobs: dict[str, dict] = {}

    def create(self, job_id: str, genome_path: str, user_id: int | None = None) -> dict:
        """Initialize a new job entry with all default fields."""
        job = {
            "job_id": job_id,
            "user_id": user_id,
            "status": "pending",
            "phase": "Initializing",
            "genome_path": genome_path,
            "sub_jobs": [],
            "slurm_jobs": [],
            "containers": [],
            "work_dir": None,
            "start_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self._jobs[job_id] = job
        LOGGER.info("Created job %s", job_id)
        return job

    def get(self, job_id: str) -> dict | None:
        """Get a job by ID, or None if not found."""
        return self._jobs.get(job_id)

    def exists(self, job_id: str) -> bool:
        return job_id in self._jobs

    def update(self, job_id: str, **fields):
        """Update one or more fields on a job."""
        if job_id in self._jobs:
            self._jobs[job_id].update(fields)

    def append_log(self, job_id: str, line: str):
        """Append a line to a job's log output."""
        if job_id in self._jobs:
            self._jobs[job_id]["logs"] = self._jobs[job_id].get("logs", "") + line + "\n"

    def add_slurm_job(self, job_id: str, slurm_id: str, rule: str):
        """Register a newly discovered SLURM sub-job."""
        if job_id in self._jobs:
            self._jobs[job_id]["slurm_jobs"].append({
                "job_id": slurm_id,
                "rule": rule,
                "status": "SUBMITTED",
                "time": "00:00:00",
            })

    def add_container(self, job_id: str, container_info: dict):
        """Register a container discovered from log parsing."""
        if job_id in self._jobs:
            self._jobs[job_id]["containers"].append(container_info)

    def get_slurm_jobs(self, job_id: str) -> list[dict]:
        """Get the slurm_jobs list for a job."""
        job = self._jobs.get(job_id)
        return job.get("slurm_jobs", []) if job else []

    def get_status(self, job_id: str) -> str | None:
        """Get just the status field for a job."""
        job = self._jobs.get(job_id)
        return job.get("status") if job else None


# Module-level singleton
job_store = JobStore()
