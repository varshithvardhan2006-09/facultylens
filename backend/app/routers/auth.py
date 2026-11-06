"""Login, refresh (rotating, httpOnly cookie), logout, change password, me."""

from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.auth.deps import Db, User, get_user_allow_pw_change
from app.auth.security import (
    create_access_token,
    hash_password_async,
    hash_refresh_token,
    new_refresh_token,
    verify_password_async,
)
from app.config import get_settings
from app.limiter import limiter
from app.schemas.auth import ChangePasswordIn, LoginIn, TokenOut
from app.schemas.users import UserOut, normalise_roll_no
from app.services.audit import record
from app.utils import now, to_jsonable

router = APIRouter(prefix="/auth", tags=["auth"])
REFRESH_DAYS_FALLBACK = 7


def user_out(user: dict[str, Any]) -> UserOut:
    return UserOut.model_validate(to_jsonable(user))


async def _issue(db: Db, response: Response, user: User) -> TokenOut:
    """Create an access token and a fresh refresh token (stored hashed, sent as a cookie)."""
    settings = get_settings()
    token, token_hash = new_refresh_token()
    days = settings.jwt_refresh_days or REFRESH_DAYS_FALLBACK
    await db.refresh_tokens.insert_one(
        {
            "jti_hash": token_hash,
            "user_id": user["_id"],
            "created_at": now(),
            "expires_at": now() + timedelta(days=days),
            "revoked": False,
        }
    )
    response.set_cookie(
        settings.refresh_cookie_name,
        token,
        max_age=days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/api/auth",
    )
    access, expires_in = create_access_token(user)
    return TokenOut(access_token=access, expires_in=expires_in, user=user_out(user))


REUSE_GRACE = timedelta(seconds=10)


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(get_settings().refresh_cookie_name, path="/api/auth")


def _session_ended(detail: str) -> JSONResponse:
    """401 that also deletes the cookie, so a dead token isn't sent again on every page load."""
    response = JSONResponse({"detail": detail}, status_code=status.HTTP_401_UNAUTHORIZED)
    _clear_cookie(response)
    return response


def _bad_login() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password.")


@router.post("/login", response_model=TokenOut)
@limiter.limit(lambda: get_settings().login_rate_limit)
async def login(request: Request, response: Response, body: LoginIn, db: Db) -> TokenOut:
    username = body.username.strip()
    query = (
        {"email": username.lower()} if "@" in username else {"roll_no": normalise_roll_no(username)}
    )
    # A blank username must not match the first account that has no roll number.
    user = await db.users.find_one(query) if username else None
    ok = await verify_password_async(body.password, user.get("password_hash") if user else None)
    if not user or not ok or not user.get("is_active", True):
        raise _bad_login()
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"last_login_at": now()}})
    return await _issue(db, response, user)


@router.post(
    "/refresh",
    response_model=TokenOut,
    responses={204: {"description": "No session cookie: nothing to refresh (signed out)"}},
)
async def refresh(request: Request, response: Response, db: Db) -> TokenOut | Response:
    token = request.cookies.get(get_settings().refresh_cookie_name)
    if not token:
        # Not an error: the app asks on every load whether a session exists.
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    token_hash = hash_refresh_token(token)
    doc = await db.refresh_tokens.find_one_and_update(
        {"jti_hash": token_hash, "revoked": False, "expires_at": {"$gt": now()}},
        {"$set": {"revoked": True, "rotated_at": now()}},
    )
    if doc is None:
        reused = await db.refresh_tokens.find_one({"jti_hash": token_hash, "revoked": True})
        rotated = (reused or {}).get("rotated_at")
        if rotated and now() - rotated <= REUSE_GRACE:
            # Two tabs opened together both send the same token: that isn't theft.
            user = await db.users.find_one({"_id": reused["user_id"]})
            if user and user.get("is_active", True):
                return await _issue(db, response, user)
        elif rotated:
            # A rotated token came back later: assume it was stolen and end every session.
            await db.refresh_tokens.update_many(
                {"user_id": reused["user_id"]},
                {"$set": {"revoked": True}, "$unset": {"rotated_at": ""}},
            )
        return _session_ended("Session expired")
    user = await db.users.find_one({"_id": doc["user_id"]})
    if not user or not user.get("is_active", True):
        return _session_ended("Account not active")
    return await _issue(db, response, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, db: Db) -> Response:
    token = request.cookies.get(get_settings().refresh_cookie_name)
    if token:
        await db.refresh_tokens.update_one(
            {"jti_hash": hash_refresh_token(token)}, {"$set": {"revoked": True}}
        )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_cookie(response)
    return response


@router.post("/change-password", response_model=TokenOut)
async def change_password(
    body: ChangePasswordIn,
    response: Response,
    db: Db,
    user: Annotated[User, Depends(get_user_allow_pw_change)],
) -> TokenOut:
    if not await verify_password_async(body.current_password, user.get("password_hash")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The current password is wrong.")
    new_hash = await hash_password_async(body.new_password)
    await db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_hash": new_hash,
                "must_change_pw": False,
                "password_changed_at": now(),
            }
        },
    )
    await db.refresh_tokens.update_many(
        {"user_id": user["_id"]}, {"$set": {"revoked": True}, "$unset": {"rotated_at": ""}}
    )
    await record(db, user, "auth.change_password", str(user["_id"]))
    user = await db.users.find_one({"_id": user["_id"]})
    return await _issue(db, response, user)


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_user_allow_pw_change)]) -> UserOut:
    return user_out(user)
