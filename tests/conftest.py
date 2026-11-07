import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db import Base, get_session
from app.main import app
from app.models import User

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5433/shortener_test"
)


@pytest.fixture
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("TRUNCATE links, users RESTART IDENTITY CASCADE"))
    yield engine
    await engine.dispose()


@pytest.fixture
async def sessionmaker(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def client(sessionmaker):
    async def override():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(client, sessionmaker):
    async def make(username="alice", role="user"):
        await client.post("/auth/register", json={"username": username, "password": "secret123"})
        if role != "user":
            async with sessionmaker() as session:
                await session.execute(update(User).where(User.username == username).values(role=role))
                await session.commit()
        response = await client.post("/auth/token", data={"username": username, "password": "secret123"})
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return make
