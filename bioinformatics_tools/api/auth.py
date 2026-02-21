"""
Authentication utilities for the BSP API.

Handles password hashing, JWT creation/verification, and the FastAPI dependency
that extracts the current user from a Bearer token on every protected request.

Required environment variables:
    BSP_SECRET_KEY  — secret used to sign JWTs. App refuses to start without it.
"""
import logging
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

from bioinformatics_tools.api.database import get_db

LOGGER = logging.getLogger(__name__)

# --- Secret key (required) ---------------------------------------------------

_SECRET_KEY = os.getenv('BSP_SECRET_KEY')
if not _SECRET_KEY:
    raise RuntimeError(
        'BSP_SECRET_KEY environment variable is not set. '
        'The API cannot start without a secret key for signing tokens.'
    )

ALGORITHM = 'HS256'
TOKEN_EXPIRE_MINUTES = 60 * 24 * 7   # 1 week

# --- Password hashing --------------------------------------------------------

_pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# --- JWT ---------------------------------------------------------------------

def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {
        'sub': str(user_id),
        'username': username,
        'exp': expire,
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token has expired')
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token')


# --- FastAPI dependency ------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/v1/auth/login')


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    FastAPI dependency. Validates the Bearer token and returns the full user row
    as a dict with keys: user_id, username, cluster_host, cluster_username.

    Raises 401 if the token is missing, invalid, or the user no longer exists.
    """
    payload = decode_token(token)
    user_id = int(payload['sub'])

    with get_db() as db:
        row = db.execute(
            'SELECT id, username, cluster_host, cluster_username FROM users WHERE id = ?',
            (user_id,)
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found')

    return {
        'user_id': row['id'],
        'username': row['username'],
        'cluster_host': row['cluster_host'],
        'cluster_username': row['cluster_username'],
    }
