import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LinkCreate(BaseModel):
    original_url: HttpUrl
    expires_at: datetime | None = None
    max_clicks: int | None = Field(default=None, gt=0)


class LinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    original_url: str
    code: uuid.UUID
    expires_at: datetime | None
    clicks: int
    max_clicks: int | None
    deleted_at: datetime | None
