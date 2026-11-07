import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, and_, func, or_
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

ROLE_LIMITS = {"user": 3, "premium": 5}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str]
    role: Mapped[str] = mapped_column(String(16), default="user")


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    original_url: Mapped[str]
    code: Mapped[uuid.UUID] = mapped_column(unique=True, default=uuid.uuid4)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    clicks: Mapped[int] = mapped_column(default=0)
    max_clicks: Mapped[int | None]
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @staticmethod
    def is_active():
        return and_(
            Link.deleted_at.is_(None),
            or_(Link.expires_at.is_(None), Link.expires_at > func.now()),
            or_(Link.max_clicks.is_(None), Link.clicks < Link.max_clicks),
        )
