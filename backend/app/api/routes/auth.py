from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentToken, CurrentUser, DbSession
from app.core import rate_limit
from app.core.config import get_settings
from app.core.security import DUMMY_HASH, create_access_token, hash_password, revoked_token_key, verify_password
from app.db.models import User
from app.services.cache import get_cache
from app.services.quotas import usage_summary

router = APIRouter(prefix="/auth", tags=["Auth"])
settings = get_settings()


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


async def _find_user(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(func.lower(User.email) == email.lower()))
    return result.scalars().first()


@router.post("/signup")
async def signup(user: UserCreate, request: Request, session: DbSession):
    await rate_limit.enforce(
        "signup", rate_limit.client_ip(request), settings.signup_per_hour, 3600,
        "Too many accounts created from this network. Try again later.",
    )
    if await _find_user(session, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    # bcrypt is deliberately slow; keep it off the event loop
    password_hash = await run_in_threadpool(hash_password, user.password)
    session.add(User(email=user.email.lower(), password=password_hash))
    await session.commit()
    return {"message": "Account created successfully"}


@router.post("/login")
async def login(user: UserLogin, request: Request, session: DbSession):
    message = "Too many sign-in attempts. Wait a few minutes and try again."
    # Per network, against scanning many accounts; per email, against guessing one password
    await rate_limit.enforce("login-ip", rate_limit.client_ip(request), settings.login_per_minute, 60, message)
    await rate_limit.enforce("login-email", user.email, settings.login_per_email_per_15min, 900, message)

    db_user = await _find_user(session, user.email)
    hashed = db_user.password if db_user else DUMMY_HASH
    valid = await run_in_threadpool(verify_password, user.password, hashed)
    if not db_user or not valid:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return {"access_token": create_access_token(db_user.id), "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(token: CurrentToken):
    # Revoke this token until it would have expired anyway
    if token.token_id:
        remaining = int((token.expires_at - datetime.now(UTC)).total_seconds())
        if remaining > 0:
            await get_cache().set(revoked_token_key(token.token_id), "1", remaining)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
async def me(user: CurrentUser, session: DbSession):
    return {"id": user.id, "email": user.email, "usage": await usage_summary(session, user.id)}
