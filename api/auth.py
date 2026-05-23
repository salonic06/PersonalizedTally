from __future__ import annotations

import os
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, Request, status

Role = Literal["owner", "worker"]

SESSION_USER = "user"
SESSION_ROLE = "role"


def web_secret() -> str:
    return os.environ.get("PT_WEB_SECRET", "dev-only-change-PT_WEB_SECRET-in-production")


def set_session(request: Request, username: str, role: Role) -> None:
    request.session[SESSION_USER] = username
    request.session[SESSION_ROLE] = role


def clear_session(request: Request) -> None:
    request.session.clear()


def current_user(request: Request) -> tuple[str, Role] | None:
    user = request.session.get(SESSION_USER)
    role = request.session.get(SESSION_ROLE)
    if not user or role not in ("owner", "worker"):
        return None
    return str(user), role  # type: ignore[return-value]


def require_user(request: Request) -> tuple[str, Role]:
    pair = current_user(request)
    if pair is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")
    return pair


def require_roles(*roles: Role):
    def _dep(request: Request) -> tuple[str, Role]:
        user, role = require_user(request)
        if role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires role: {', '.join(roles)}",
            )
        return user, role

    return _dep


UserDep = Annotated[tuple[str, Role], Depends(require_user)]
OwnerDep = Annotated[tuple[str, Role], Depends(require_roles("owner"))]
