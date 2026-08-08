from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user_id(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> UUID:
    error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        return UUID(str(payload["sub"]))
    except (ValueError, KeyError) as exc:
        raise error from exc


CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]
