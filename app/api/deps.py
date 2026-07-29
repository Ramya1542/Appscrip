"""Shared API dependencies (DB session, current user)."""
from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_session
from app.models.user import User
from app.services.users import get_user_by_id

bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exc
        user_id = int(sub)
    except (jwt.PyJWTError, ValueError, TypeError):
        raise credentials_exc

    user = await get_user_by_id(session, user_id)
    if user is None:
        raise credentials_exc

    # Expose the user id so the exception-logging middleware can attribute errors.
    request.state.user_id = user.id
    return user


# Re-export the session dependency for convenience.
DBSession = get_session
