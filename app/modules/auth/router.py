from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.dependencies.database import DatabaseSession
from app.modules.auth.schemas import TokenResponse, UserCreate, UserResponse
from app.modules.auth.service import AuthService

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, db: DatabaseSession) -> UserResponse:
    user = AuthService(db).register(data)
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        is_active=user.is_active,
    )


@router.post("/login", response_model=TokenResponse)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DatabaseSession,
) -> TokenResponse:
    return AuthService(db).login(form.username, form.password)
