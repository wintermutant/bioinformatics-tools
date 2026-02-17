"""
Local workflow execution endpoints (quick_example, fresh_test).

These run touch-only snakemake workflows locally — no SSH/SLURM required.
"""
import logging

from fastapi import APIRouter

router = APIRouter(prefix="/v1/workflows", tags=["workflows"])

LOGGER = logging.getLogger(__name__)


@router.post("/run_quick_example")
async def run_quick_example():
    """Run the quick_example workflow (touch-only, with DB cache restore/store)."""
    # TODO: instantiate WorkflowBase and call do_quick_example
    return {"success": True, "message": "quick_example placeholder"}


@router.post("/run_fresh_test")
async def run_fresh_test():
    """Run the fresh_test workflow (touch-only, no cache, snakemake runs all rules)."""
    # TODO: instantiate WorkflowBase and call do_fresh_test
    return {"success": True, "message": "fresh_test placeholder"}
