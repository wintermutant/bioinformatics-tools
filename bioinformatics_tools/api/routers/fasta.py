"""
Fasta file processing endpoints
"""
import logging
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from bioinformatics_tools.file_classes.Fasta import Fasta
from bioinformatics_tools.api.models import GenericRequest, GenericResponse

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/fasta", tags=["fasta"])


# Endpoints
@router.get("/health")
async def health_check():
    """Test endpoint to verify API is working"""
    return {"status": "success"}


@router.post("/example", response_model=GenericResponse)
async def gc_content(request: GenericRequest):
    return 0
    


def generic_fileclass_api(file_path: str | Path, class_: type):
    '''Less code for adding API routes for FileClasses'''
    try:
        file_path = Path(file_path)

        # Validate file exists
        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {file_path}"
            )

        # Initialize Fasta in module mode
        print('About to initialize...')
        filetype_class_initd = class_(file=str(file_path), run_mode='module')
        print('Fasta initialized correctly.')

        # Validate the file
        if not filetype_class_initd.valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid FASTA file: {file_path}"
            )

        return filetype_class_initd

    except HTTPException:
        raise
    except Exception as e:
        LOGGER.exception("Error within generic_fileclass_api")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        ) from e


@router.post("/gc_content", response_model=GenericResponse)
async def calculate_gc_content(request: GenericRequest):
    """
    Calculate GC content for each sequence in a FASTA file
    """
    fasta_class = generic_fileclass_api(request.file_path, Fasta)
    try:
        data = fasta_class.do_gc_content(origin='api')
        return GenericResponse(
            status="success",
            data=data,
            message=f"GC content calculated for {data} sequences"
        )
    except Exception as e:
        LOGGER.exception("Error calculating GC content")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        ) from e


@router.post("/gc_content_total", response_model=GenericResponse)
async def calculate_gc_content_total(request: GenericRequest):
    """
    Calculate GC content for each sequence in a FASTA file
    """
    fasta_class = generic_fileclass_api(request.file_path, Fasta)
    try:
        data = fasta_class.do_gc_content_total(origin='api')
        return GenericResponse(
            status="success",
            data=data,
            message=f"GC content calculated for {data} sequences"
        )
    except Exception as e:
        LOGGER.exception("Error calculating GC content")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        ) from e