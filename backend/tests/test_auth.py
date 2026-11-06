from datetime import timedelta

import jwt
import pytest

from app.auth.security import ALGORITHM
from app.config import get_settings
from app.utils import now
from tests.conftest import PASSWORD, ROLL_NUMBERS, login, make_user


async def test_login_with_email_and_with_roll_number(client, mongo):
    await make_user(mongo, "faculty", email="t@test.edu", department_id=None)
    await make_user(mongo, "student", roll_no=ROLL_NUMBERS[1])
    r = await client.post("/api/auth/login", json={"username": "T@Test.edu", "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["user"]["role"] == "faculty"
    assert "password_hash" not in body["user"]
    cookie = r.headers["set-cookie"]
    assert "fl_refresh=" in cookie and "HttpOnly" in cookie and "Path=/api/auth" in cookie
    assert "samesite=strict" in cookie.lower()
    # Roll numbers are case-insensitive.
    r = await client.post(
        "/api/auth/login", json={"username": ROLL_NUMBERS[1].lower(), "password": PASSWORD}
    )
    assert r.status_code == 200 and r.json()["user"]["roll_no"] == ROLL_NUMBERS[1]


@pytest.mark.parametrize("username", ["t@test.edu", "nobody@test.edu"])
async def test_bad_credentials_give_same_401(client, mongo, username):
    await make_user(mongo, "admin", email="t@test.edu")
    r = await client.post("/api/auth/login", json={"username": username, "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Wrong username or password."


async def test_inactive_user_cannot_login(client, mongo):
    await make_user(mongo, "admin", email="t@test.edu", is_active=False)
    r = await client.post("/api/auth/login", json={"username": "t@test.edu", "password": PASSWORD})
    assert r.status_code == 401


async def test_login_is_rate_limited(client, mongo):
    for _ in range(5):
        await client.post("/api/auth/login", json={"username": "x@test.edu", "password": "nope"})
    r = await client.post("/api/auth/login", json={"username": "x@test.edu", "password": "nope"})
    assert r.status_code == 429


async def test_me_requires_a_valid_token(client, mongo):
    assert (await client.get("/api/auth/me")).status_code == 401
    bad = {"Authorization": "Bearer not-a-token"}
    assert (await client.get("/api/auth/me", headers=bad)).status_code == 401


async def test_expired_access_token_is_rejected(client, mongo):
    user = await make_user(mongo, "admin", email="t@test.edu")
    expired = jwt.encode(
        {"sub": str(user["_id"]), "type": "access", "exp": now() - timedelta(minutes=1)},
        get_settings().jwt_secret,
        algorithm=ALGORITHM,
    )
    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and r.json()["detail"] == "Session expired"


async def test_refresh_rotates_and_detects_reuse(client, mongo):
    await make_user(mongo, "admin", email="t@test.edu")
    await login(client, "t@test.edu")
    first = client.cookies.get("fl_refresh")
    r = await client.post("/api/auth/refresh")
    assert r.status_code == 200 and r.json()["access_token"]
    second = client.cookies.get("fl_refresh")
    assert second and second != first
    # Replaying the rotated token fails and revokes every session of that user.
    client.cookies.clear()
    client.cookies.set("fl_refresh", first)
    r = await client.post("/api/auth/refresh")
    assert r.status_code == 401
    assert 'fl_refresh=""' in r.headers["set-cookie"] or "Max-Age=0" in r.headers["set-cookie"]
    assert await mongo.refresh_tokens.count_documents({"revoked": False}) == 0


async def test_refresh_without_cookie_is_no_content(client, mongo):
    r = await client.post("/api/auth/refresh")
    assert r.status_code == 204 and r.content == b""


async def test_logout_revokes_refresh_token(client, mongo):
    await make_user(mongo, "admin", email="t@test.edu")
    await login(client, "t@test.edu")
    token = client.cookies.get("fl_refresh")
    assert (await client.post("/api/auth/logout")).status_code == 204
    client.cookies.clear()
    client.cookies.set("fl_refresh", token)
    r = await client.post("/api/auth/refresh")
    assert r.status_code == 401


async def test_temporary_password_must_be_changed_first(client, mongo):
    await make_user(mongo, "admin", email="t@test.edu", must_change_pw=True)
    headers = await login(client, "t@test.edu")
    me = await client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["must_change_pw"] is True
    blocked = await client.get("/api/users", headers=headers)
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "password_change_required"

    weak = await client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "short"},
    )
    assert weak.status_code == 422
    wrong = await client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "nope-nope-nope", "new_password": "a-much-longer-one"},
    )
    assert wrong.status_code == 400
    ok = await client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "a-much-longer-one"},
    )
    assert ok.status_code == 200 and ok.json()["user"]["must_change_pw"] is False
    new_headers = {"Authorization": f"Bearer {ok.json()['access_token']}"}
    assert (await client.get("/api/users", headers=new_headers)).status_code == 200
    # The old password no longer works.
    r = await client.post("/api/auth/login", json={"username": "t@test.edu", "password": PASSWORD})
    assert r.status_code == 401


async def test_deactivated_user_loses_access_immediately(client, mongo):
    user = await make_user(mongo, "admin", email="t@test.edu")
    headers = await login(client, "t@test.edu")
    await mongo.users.update_one({"_id": user["_id"]}, {"$set": {"is_active": False}})
    assert (await client.get("/api/auth/me", headers=headers)).status_code == 401
