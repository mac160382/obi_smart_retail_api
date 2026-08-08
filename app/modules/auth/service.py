from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository
from app.modules.auth.schemas import TokenResponse, UserCreate


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)

    def register(self, data: UserCreate) -> User:
        if self.users.get_by_username(data.username):
            raise HTTPException(status_code=409, detail="El usuario ya existe")
        if self.users.get_by_email(str(data.email)):
            raise HTTPException(status_code=409, detail="El correo ya existe")

        user = User(
            username=data.username,
            email=str(data.email),
            password_hash=hash_password(data.password),
        )
        try:
            self.users.add(user)
            self.db.commit()
            self.db.refresh(user)
            return user
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(status_code=409, detail="Usuario o correo duplicado") from exc

    def login(self, username: str, password: str) -> TokenResponse:
        user = self.users.get_by_username_or_email(username)
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario o contraseña incorrectos",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Usuario inactivo")

        token = create_access_token(str(user.id), {"username": user.username})
        return TokenResponse(
            access_token=token,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )
