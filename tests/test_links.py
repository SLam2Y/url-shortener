import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.models import Link


async def create(client, headers, url="https://example.com/", **extra):
    return await client.post("/links", json={"original_url": url, **extra}, headers=headers)


async def test_create_and_redirect(client, make_user):
    headers = await make_user()
    response = await create(client, headers)
    assert response.status_code == 201
    code = response.json()["code"]

    response = await client.get(f"/{code}")
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/"

    links = (await client.get("/links", headers=headers)).json()
    assert links[0]["clicks"] == 1


async def test_same_url_returns_existing(client, make_user):
    headers = await make_user()
    first = (await create(client, headers)).json()
    second = await create(client, headers)
    assert second.status_code == 200
    assert second.json()["code"] == first["code"]
    assert len((await client.get("/links", headers=headers)).json()) == 1


async def test_same_url_different_users(client, make_user):
    alice = await make_user("alice")
    bob = await make_user("bob")
    a = (await create(client, alice)).json()
    b = (await create(client, bob)).json()
    assert a["code"] != b["code"]


async def test_limit_user(client, make_user):
    headers = await make_user(role="user")
    for i in range(3):
        assert (await create(client, headers, f"https://example.com/{i}")).status_code == 201
    assert (await create(client, headers, "https://example.com/extra")).status_code == 403


async def test_limit_premium(client, make_user):
    headers = await make_user(role="premium")
    for i in range(5):
        assert (await create(client, headers, f"https://example.com/{i}")).status_code == 201
    assert (await create(client, headers, "https://example.com/extra")).status_code == 403


async def test_deleted_link_frees_limit(client, make_user):
    headers = await make_user()
    ids = [(await create(client, headers, f"https://example.com/{i}")).json()["id"] for i in range(3)]
    await client.delete(f"/links/{ids[0]}", headers=headers)
    assert (await create(client, headers, "https://example.com/new")).status_code == 201


async def test_expired_by_date(client, make_user, sessionmaker):
    headers = await make_user()
    link = (await create(client, headers)).json()
    async with sessionmaker() as session:
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        await session.execute(update(Link).where(Link.id == link["id"]).values(expires_at=past))
        await session.commit()
    assert (await client.get(f"/{link['code']}")).status_code == 419


async def test_expired_by_clicks(client, make_user):
    headers = await make_user()
    code = (await create(client, headers, max_clicks=2)).json()["code"]
    assert (await client.get(f"/{code}")).status_code == 302
    assert (await client.get(f"/{code}")).status_code == 302
    assert (await client.get(f"/{code}")).status_code == 419


async def test_expired_link_frees_limit_and_new_code(client, make_user):
    headers = await make_user()
    old = (await create(client, headers, max_clicks=1)).json()["code"]
    await client.get(f"/{old}")
    response = await create(client, headers)
    assert response.status_code == 201
    assert response.json()["code"] != old


async def test_not_found(client):
    assert (await client.get(f"/{uuid.uuid4()}")).status_code == 404
    assert (await client.get("/not-a-uuid")).status_code == 404


async def test_soft_delete(client, make_user):
    headers = await make_user()
    link = (await create(client, headers)).json()
    assert (await client.delete(f"/links/{link['id']}", headers=headers)).status_code == 204
    assert (await client.get(f"/{link['code']}")).status_code == 404
    assert (await client.delete(f"/links/{link['id']}", headers=headers)).status_code == 404
    links = (await client.get("/links", headers=headers)).json()
    assert links[0]["deleted_at"] is not None


async def test_cannot_delete_foreign_link(client, make_user):
    alice = await make_user("alice")
    bob = await make_user("bob")
    link = (await create(client, alice)).json()
    assert (await client.delete(f"/links/{link['id']}", headers=bob)).status_code == 404
    assert (await client.get(f"/{link['code']}")).status_code == 302


async def test_list_only_own(client, make_user):
    alice = await make_user("alice")
    bob = await make_user("bob")
    await create(client, alice)
    assert (await client.get("/links", headers=bob)).json() == []


async def test_parallel_clicks_are_atomic(client, make_user):
    headers = await make_user()
    code = (await create(client, headers, max_clicks=5)).json()["code"]
    responses = await asyncio.gather(*(client.get(f"/{code}") for _ in range(10)))
    statuses = [r.status_code for r in responses]
    assert statuses.count(302) == 5
    assert statuses.count(419) == 5
    assert (await client.get("/links", headers=headers)).json()[0]["clicks"] == 5
