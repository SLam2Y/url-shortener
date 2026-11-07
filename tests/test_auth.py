from app.auth import hash_password, verify_password


def test_argon2id_hash():
    password_hash = hash_password("secret123")
    assert password_hash.startswith("$argon2id$")
    assert verify_password("secret123", password_hash)
    assert not verify_password("wrong", password_hash)


async def test_register_and_login(client):
    response = await client.post("/auth/register", json={"username": "bob", "password": "secret123"})
    assert response.status_code == 201
    assert response.json()["role"] == "user"

    response = await client.post("/auth/token", data={"username": "bob", "password": "secret123"})
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"


async def test_register_duplicate(client):
    await client.post("/auth/register", json={"username": "bob", "password": "secret123"})
    response = await client.post("/auth/register", json={"username": "bob", "password": "secret123"})
    assert response.status_code == 409


async def test_login_wrong_password(client):
    await client.post("/auth/register", json={"username": "bob", "password": "secret123"})
    response = await client.post("/auth/token", data={"username": "bob", "password": "nope"})
    assert response.status_code == 401


async def test_links_require_token(client):
    assert (await client.get("/links")).status_code == 401
    assert (await client.get("/links", headers={"Authorization": "Bearer garbage"})).status_code == 401
