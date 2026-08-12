from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    user_id: UUID
    expires_at: datetime


def get_authenticated_user(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> AuthenticatedUser:
    error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        return AuthenticatedUser(
            user_id=UUID(str(payload["sub"])),
            expires_at=datetime.fromtimestamp(float(payload["exp"]), UTC),
        )
    except (TypeError, ValueError, KeyError) as exc:
        raise error from exc


def get_current_user_id(
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
) -> UUID:
    return user.user_id


CurrentAuthenticatedUser = Annotated[
    AuthenticatedUser,
    Depends(get_authenticated_user),
]
CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]
