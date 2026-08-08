from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.auth.models import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username))

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def get_by_username_or_email(self, value: str) -> User | None:
        return self.db.scalar(
            select(User).where(or_(User.username == value, User.email == value))
        )

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user
