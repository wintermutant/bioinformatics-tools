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


# --- Auth models -------------------------------------------------------------

class UserRegister(BaseModel):
    username: str
    password: str
    cluster_host: str
    cluster_username: str
    private_key: str   # plaintext SSH private key — encrypted before storage, never returned


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str   # always "bearer"


class UserProfile(BaseModel):
    user_id: int
    username: str
    cluster_host: str
    cluster_username: str
    created_at: str
