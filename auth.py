"""
auth.py  —  Admin authentication via HTTP Basic + JWT bearer token.

Flow:
  1. POST /admin/login  →  returns a signed JWT (24 h expiry)
  2. All /admin/* routes require  Authorization: Bearer <token>
"""
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import settings

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24
bearer_scheme = HTTPBearer()


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode(payload, settings.admin_secret_token, algorithm=ALGORITHM)


def verify_admin_credentials(username: str, password: str) -> bool:
    return (
        username == settings.admin_username
        and password == settings.admin_password
    )


def get_current_admin(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> dict:
    """FastAPI dependency — validates JWT and returns the payload."""
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, settings.admin_secret_token, algorithms=[ALGORITHM]
        )
        if payload.get("role") != "admin":
            raise ValueError("Not an admin token")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired. Please log in again.",
        )
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )
