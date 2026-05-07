from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import API_BASIC_AUTH_PASSWORD, API_BASIC_AUTH_USERNAME


http_basic = HTTPBasic()


def authenticate(credentials: HTTPBasicCredentials = Depends(http_basic)) -> str:
    username_is_valid = secrets.compare_digest(credentials.username, API_BASIC_AUTH_USERNAME)
    password_is_valid = secrets.compare_digest(credentials.password, API_BASIC_AUTH_PASSWORD)
    if not (username_is_valid and password_is_valid):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
