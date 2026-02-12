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


class DaneEntry(BaseModel):
    value: str


class SlurmSend(BaseModel):
    script: str


class GenomeSend(BaseModel):
    genome_path: str
