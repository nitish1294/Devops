from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role
from app.core.logging import actor_var
from app.core.security import decode_token
from app.db.postgres import get_db
from app.models.user import User

bearer = HTTPBearer(auto_error=False)

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


async def current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if creds is None:
        raise CREDENTIALS_ERROR
    try:
        payload = decode_token(creds.credentials, expect="access")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, sign in again")
    except jwt.PyJWTError:
        raise CREDENTIALS_ERROR

    user_id = payload.get("sub")
    if user_id is None:
        raise CREDENTIALS_ERROR

    user = (await db.execute(select(User).where(User.id == int(user_id)))).unique().scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is inactive")

    # Every log line for the rest of this request names who made it.
    actor_var.set(user.email)
    return user


CurrentUser = Annotated[User, Depends(current_user)]
Db = Annotated[AsyncSession, Depends(get_db)]


def require_roles(*roles: Role):
    """Route guard: `_=Depends(require_roles(Role.ADMIN, Role.HR_MANAGER))`."""

    allowed = {str(r) for r in roles}

    async def guard(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Your role ({user.role}) cannot perform this action",
            )
        return user

    return guard


# Common combinations, named for readability at the call site.
can_manage_users = require_roles(Role.ADMIN)
can_manage_jobs = require_roles(Role.ADMIN, Role.HR_MANAGER, Role.RECRUITER)
can_manage_offers = require_roles(Role.ADMIN, Role.HR_MANAGER)
can_move_pipeline = require_roles(Role.ADMIN, Role.HR_MANAGER, Role.RECRUITER, Role.HIRING_MANAGER)


# Annotated aliases so routes read `actor: ManageJobs` instead of stacking Depends.
ManageUsers = Annotated[User, Depends(can_manage_users)]
ManageJobs = Annotated[User, Depends(can_manage_jobs)]
ManageOffers = Annotated[User, Depends(can_manage_offers)]
MovePipeline = Annotated[User, Depends(can_move_pipeline)]
