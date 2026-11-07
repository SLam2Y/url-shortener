import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.db import get_session
from app.models import ROLE_LIMITS, Link, User
from app.schemas import LinkCreate, LinkOut, Token, UserCreate, UserOut

app = FastAPI(title="URL shortener")

Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@app.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, session: Session):
    if await session.scalar(select(User).where(User.username == data.username)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Username taken")
    user = User(username=data.username, password_hash=hash_password(data.password))
    session.add(user)
    await session.commit()
    return user


@app.post("/auth/token", response_model=Token)
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], session: Session):
    user = await session.scalar(select(User).where(User.username == form.username))
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password")
    return Token(access_token=create_access_token(user.id))


async def own_link(link_id: int, user: CurrentUser, session: Session) -> Link:
    link = await session.scalar(
        select(Link).where(Link.id == link_id, Link.user_id == user.id, Link.deleted_at.is_(None))
    )
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    return link


@app.post("/links", response_model=LinkOut)
async def create_link(data: LinkCreate, user: CurrentUser, session: Session, response: Response):
    await session.execute(select(User.id).where(User.id == user.id).with_for_update())
    url = str(data.original_url)
    existing = await session.scalar(
        select(Link).where(Link.user_id == user.id, Link.original_url == url, Link.is_active())
    )
    if existing:
        return existing
    active_count = await session.scalar(
        select(func.count()).select_from(Link).where(Link.user_id == user.id, Link.is_active())
    )
    if active_count >= ROLE_LIMITS[user.role]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Active links limit reached")
    link = Link(user_id=user.id, original_url=url, expires_at=data.expires_at, max_clicks=data.max_clicks)
    session.add(link)
    await session.commit()
    response.status_code = status.HTTP_201_CREATED
    return link


@app.get("/links", response_model=list[LinkOut])
async def list_links(user: CurrentUser, session: Session):
    result = await session.scalars(select(Link).where(Link.user_id == user.id).order_by(Link.id))
    return result.all()


@app.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(link: Annotated[Link, Depends(own_link)], session: Session):
    link.deleted_at = func.now()
    await session.commit()


@app.get("/{code}")
async def follow(code: str, session: Session):
    try:
        code = uuid.UUID(code)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    original_url = await session.scalar(
        update(Link)
        .where(Link.code == code, Link.is_active())
        .values(clicks=Link.clicks + 1)
        .returning(Link.original_url)
    )
    await session.commit()
    if original_url:
        return RedirectResponse(original_url, status_code=status.HTTP_302_FOUND)
    link = await session.scalar(select(Link).where(Link.code == code, Link.deleted_at.is_(None)))
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    raise HTTPException(419, "Link expired")
