import logging

import jwt
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import CurrentUser, Db
from app.core.logging import actor_var
from app.core.ratelimit import login_limiter
from app.core.security import (
    create_access_token, create_refresh_token, decode_token,
    hash_password, password_problems, verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest, LoginRequest, RefreshRequest, TokenResponse,
)
from app.schemas.common import Message
from app.schemas.user import UserOut
from app.services import activity

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger("hrms.auth")


def _tokens(user: User) -> TokenResponse:
    access, expires_in = create_access_token(str(user.id), user.role)
    refresh, _ = create_refresh_token(str(user.id), user.role)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, db: Db):
    """Sign in.

    Throttled per email and per client address. Both are counted because
    limiting only by email lets one host walk a list of accounts, and limiting
    only by address lets a botnet grind a single account.
    """
    email = payload.email.lower()
    client_ip = request.client.host if request.client else "unknown"

    for key in (f"email:{email}", f"ip:{client_ip}"):
        wait = login_limiter.retry_after(key)
        if wait:
            log.warning("login blocked", extra={"key": key, "retry_after": wait})
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Too many failed attempts. Try again in {wait} seconds.",
                headers={"Retry-After": str(wait)},
            )

    user = (
        (await db.execute(select(User).where(User.email == email)))
        .unique()
        .scalar_one_or_none()
    )

    # One message for both cases, so the response cannot be used to discover
    # which addresses have accounts.
    if not user or not verify_password(payload.password, user.password_hash):
        remaining = min(
            login_limiter.record_failure(f"email:{email}"),
            login_limiter.record_failure(f"ip:{client_ip}"),
        )
        log.warning("login failed", extra={"email": email, "remaining": remaining})
        detail = "Email or password is incorrect"
        if 0 < remaining <= 2:
            detail += f". {remaining} attempt{'s' if remaining > 1 else ''} left before a temporary lock."
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail)

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated")

    login_limiter.reset(f"email:{email}")
    login_limiter.reset(f"ip:{client_ip}")
    actor_var.set(user.email)

    await activity.log(
        "login", "user", user.id, f"{user.full_name} signed in", user.id, user.full_name
    )
    log.info("login ok", extra={"user_id": user.id, "role": user.role})
    return _tokens(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: Db):
    """Exchange a refresh token for a new pair.

    Access tokens are short-lived so a leaked one expires quickly; this is what
    keeps the user from being signed out every hour because of it.
    """
    try:
        claims = decode_token(payload.refresh_token, expect="refresh")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, sign in again")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That refresh token is not valid")

    user = (
        (await db.execute(select(User).where(User.id == int(claims["sub"]))))
        .unique()
        .scalar_one_or_none()
    )
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is inactive")

    # A fresh refresh token comes back too, so an active session rolls forward
    # rather than hitting a hard 14-day wall.
    return _tokens(user)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user


@router.post("/change-password", response_model=Message)
async def change_password(payload: ChangePasswordRequest, user: CurrentUser, db: Db):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "The new password must differ from the old one"
        )
    problems = password_problems(payload.new_password)
    if problems:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, " ".join(problems))

    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    await db.commit()

    await activity.log(
        "password_changed", "user", user.id,
        f"{user.full_name} changed their password", user.id, user.full_name,
    )
    log.info("password changed", extra={"user_id": user.id})
    return Message(detail="Password updated")
