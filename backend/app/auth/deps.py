"""Role dependencies. The user is reloaded from MongoDB on every request, so a role change or
deactivation takes effect immediately rather than when the token expires."""

from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.asynchronous.database import AsyncDatabase

from app.auth.security import decode_access_token
from app.db import get_db
from app.utils import oid

ROLES = ("admin", "hod", "faculty", "student")
_bearer = HTTPBearer(auto_error=False)

User = dict[str, Any]


def _unauthorized(message: str = "Not signed in") -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, message, headers={"WWW-Authenticate": "Bearer"}
    )


async def get_user_allow_pw_change(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncDatabase, Depends(get_db)],
) -> User:
    """Any signed-in, active user, including one who still has to change a temporary password."""
    if creds is None:
        raise _unauthorized()
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Session expired") from None
    except jwt.InvalidTokenError:
        raise _unauthorized("Invalid token") from None
    try:
        user_id = oid(payload["sub"])
    except HTTPException:
        raise _unauthorized("Invalid token") from None
    user = await db.users.find_one({"_id": user_id})
    if not user or not user.get("is_active", True):
        raise _unauthorized("Account not active")
    return user


async def get_current_user(user: Annotated[User, Depends(get_user_allow_pw_change)]) -> User:
    if user.get("must_change_pw"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            {
                "code": "password_change_required",
                "message": "Change your temporary password first.",
            },
        )
    return user


def require_roles(*roles: str):
    unknown = set(roles) - set(ROLES)
    if unknown:
        raise ValueError(f"Unknown roles: {unknown}")

    async def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user["role"] not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have access to this.")
        return user

    return dependency


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_roles("admin"))]
Db = Annotated[AsyncDatabase, Depends(get_db)]
