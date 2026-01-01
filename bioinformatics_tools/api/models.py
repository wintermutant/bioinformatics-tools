from typing import Optional

from pydantic import BaseModel, Field


class GenericRequest(BaseModel):
    '''generic request base model. Inherit from here to extend'''
    file_path: str = Field(..., description="path to file")


class GenericResponse(BaseModel):
    '''generic response base model. Inherit from here to expand'''
    status: str
    data: dict
    message: Optional[str] = None


# Request/Response Models
# class GCContentRequest(BaseModel):
#     """Request model for GC content calculation"""
#     file_path: str = Field(..., description="Path to the fasta file")
#     precision: int = Field(2, description="Decimal precision for GC content", ge=0, le=10)


# class GCContentResponse(BaseModel):
#     """Response model for GC content calculation"""
#     status: str
#     data: dict
#     message: Optional[str] = None