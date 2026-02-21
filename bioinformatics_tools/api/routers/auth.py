"""
Authentication endpoints for the BSP API.

POST /v1/auth/register  — create a new user account
POST /v1/auth/login     — exchange credentials for a JWT
GET  /v1/auth/me        — return the current user's profile (requires token)
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from bioinformatics_tools.api.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from bioinformatics_tools.api.database import get_db
from bioinformatics_tools.api.models import (
    TokenResponse,
    UserLogin,
    UserProfile,
    UserRegister,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix='/v1/auth', tags=['auth'])


@router.post('/register', status_code=status.HTTP_201_CREATED)
def register(body: UserRegister):
    """
    Create a new BSP user account.

    Stores the username, a bcrypt-hashed password, and the user's cluster
    connection details (host + username). Returns the new user_id and username.
    Does not issue a token — requires a separate login call.
    """
    created_at = datetime.now(timezone.utc).isoformat()
    password_hash = hash_password(body.password)

    try:
        with get_db() as db:
            cursor = db.execute(
                '''INSERT INTO users (username, password_hash, cluster_host, cluster_username, created_at)
                   VALUES (?, ?, ?, ?, ?)''',
                (body.username, password_hash, body.cluster_host, body.cluster_username, created_at)
            )
            user_id = cursor.lastrowid
    except Exception as exc:
        # SQLite raises IntegrityError when UNIQUE constraint on username is violated
        if 'UNIQUE' in str(exc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Username already taken'
            )
        LOGGER.exception('Unexpected error during registration')
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Registration failed')

    LOGGER.info('New user registered: %s (id=%s)', body.username, user_id)
    return {'user_id': user_id, 'username': body.username}


@router.post('/login', response_model=TokenResponse)
def login(body: UserLogin):
    """
    Exchange username + password for a JWT access token.

    Returns a generic error on any failure — never reveals whether the
    username exists.
    """
    _invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Invalid credentials'
    )

    with get_db() as db:
        row = db.execute(
            'SELECT id, username, password_hash FROM users WHERE username = ?',
            (body.username,)
        ).fetchone()

    if row is None or not verify_password(body.password, row['password_hash']):
        raise _invalid

    token = create_access_token(user_id=row['id'], username=row['username'])
    LOGGER.info('User logged in: %s', body.username)
    return TokenResponse(access_token=token, token_type='bearer')


@router.get('/me', response_model=UserProfile)
def me(current_user: dict = Depends(get_current_user)):
    """
    Return the profile of the currently authenticated user.

    Used by the frontend to hydrate state after a page refresh using a
    stored token. Never returns the password hash.
    """
    with get_db() as db:
        row = db.execute(
            'SELECT id, username, cluster_host, cluster_username, created_at FROM users WHERE id = ?',
            (current_user['user_id'],)
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    return UserProfile(
        user_id=row['id'],
        username=row['username'],
        cluster_host=row['cluster_host'],
        cluster_username=row['cluster_username'],
        created_at=row['created_at'],
    )
