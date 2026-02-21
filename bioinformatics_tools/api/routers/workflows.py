"""
Local workflow execution endpoints (quick_example, fresh_test).

These run touch-only snakemake workflows on the remote via SSH,
using the real margie.db for cache operations.
"""
import logging
import uuid

from fastapi import APIRouter, Depends

from bioinformatics_tools.api.auth import decrypt_private_key, get_current_user
from bioinformatics_tools.api.services import job_runner
from bioinformatics_tools.api.services.job_store import job_store
from bioinformatics_tools.utilities.ssh_connection import make_user_connection

router = APIRouter(prefix="/v1/workflows", tags=["workflows"])

LOGGER = logging.getLogger(__name__)


def _build_connection(current_user: dict):
    """Decrypt the user's stored private key and return a ready SSHConnection."""
    private_key = decrypt_private_key(current_user['private_key_encrypted'])
    return make_user_connection(
        current_user['cluster_host'],
        current_user['cluster_username'],
        private_key,
    )


@router.post("/run_quick_example")
async def run_quick_example(current_user: dict = Depends(get_current_user)):
    """Run the quick_example workflow (touch-only, cache restore/store with real margie.db)."""
    conn = _build_connection(current_user)
    job_id = str(uuid.uuid4())
    job_store.create(job_id, "quick_example (selftest)", user_id=current_user["user_id"])

    command = "uvx --from ~/bioinformatics-tools/ --force-reinstall dane_wf quick example"
    job_runner.submit_job(job_id, command, connection=conn)

    return {"success": True, "job_id": job_id, "message": "quick_example submitted"}


@router.post("/run_fresh_test")
async def run_fresh_test(current_user: dict = Depends(get_current_user)):
    """Run the fresh_test workflow (touch-only, unique input, always runs all rules)."""
    conn = _build_connection(current_user)
    job_id = str(uuid.uuid4())
    job_store.create(job_id, "fresh_test (selftest)", user_id=current_user["user_id"])

    command = "uvx --from ~/bioinformatics-tools/ --force-reinstall dane_wf fresh test"
    job_runner.submit_job(job_id, command, connection=conn)

    return {"success": True, "job_id": job_id, "message": "fresh_test submitted"}
