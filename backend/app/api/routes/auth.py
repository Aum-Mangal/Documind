from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession
from app.core.security import DUMMY_HASH, create_access_token, hash_password, verify_password
from app.db.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])


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
async def signup(user: UserCreate, session: DbSession):
    if await _find_user(session, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    # bcrypt is deliberately slow; keep it off the event loop
    password_hash = await run_in_threadpool(hash_password, user.password)
    session.add(User(email=user.email.lower(), password=password_hash))
    await session.commit()
    return {"message": "Account created successfully"}


@router.post("/login")
async def login(user: UserLogin, session: DbSession):
    db_user = await _find_user(session, user.email)
    hashed = db_user.password if db_user else DUMMY_HASH
    valid = await run_in_threadpool(verify_password, user.password, hashed)
    if not db_user or not valid:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return {"access_token": create_access_token(db_user.id), "token_type": "bearer"}
