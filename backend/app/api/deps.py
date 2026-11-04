from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenClaims, decode_token, revoked_token_key
from app.db.models import User
from app.db.session import get_session
from app.services.cache import get_cache

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: DbSession,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    claims = await get_token_claims(credentials)
    user = await session.get(User, claims.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    return user


async def get_token_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenClaims:
    unauthorized = HTTPException(
        status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = decode_token(credentials.credentials)
    except (jwt.InvalidTokenError, ValueError):
        raise unauthorized from None
    if claims.token_id and await get_cache().exists(revoked_token_key(claims.token_id)):
        raise unauthorized
    return claims


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentToken = Annotated[TokenClaims, Depends(get_token_claims)]
