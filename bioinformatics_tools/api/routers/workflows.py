"""
Local workflow execution endpoints (quick_example, fresh_test).

These run touch-only snakemake workflows on the remote via SSH,
using the real margie.db for cache operations.
"""
import logging
import uuid

from fastapi import APIRouter

from bioinformatics_tools.api.services.job_store import job_store
from bioinformatics_tools.api.services import job_runner

router = APIRouter(prefix="/v1/workflows", tags=["workflows"])

LOGGER = logging.getLogger(__name__)


@router.post("/run_quick_example")
async def run_quick_example():
    """Run the quick_example workflow (touch-only, cache restore/store with real margie.db)."""
    job_id = str(uuid.uuid4())
    job_store.create(job_id, "quick_example (selftest)")

    command = "uvx --from ~/bioinformatics-tools/ --force-reinstall dane_wf quick example"
    job_runner.submit_job(job_id, command)

    return {"success": True, "job_id": job_id, "message": "quick_example submitted"}


@router.post("/run_fresh_test")
async def run_fresh_test():
    """Run the fresh_test workflow (touch-only, unique input, always runs all rules)."""
    job_id = str(uuid.uuid4())
    job_store.create(job_id, "fresh_test (selftest)")

    command = "uvx --from ~/bioinformatics-tools/ --force-reinstall dane_wf fresh test"
    job_runner.submit_job(job_id, command)

    return {"success": True, "job_id": job_id, "message": "fresh_test submitted"}
