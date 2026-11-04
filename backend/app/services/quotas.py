"""Per-user quotas: daily LLM tokens, number of documents and storage used."""
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Document, UsageEvent
from app.services.llm import Usage


async def tokens_used_today(session: AsyncSession, user_id: int) -> int:
    # The quota resets at midnight UTC
    start_of_day = func.date_trunc("day", func.now(), "UTC")
    total = (await session.execute(
        select(func.coalesce(func.sum(UsageEvent.prompt_tokens + UsageEvent.completion_tokens), 0))
        .where(UsageEvent.user_id == user_id, UsageEvent.created_at >= start_of_day)
    )).scalar()
    return int(total)


async def has_ai_allowance(session: AsyncSession, user_id: int) -> bool:
    quota = get_settings().daily_token_quota
    return quota <= 0 or await tokens_used_today(session, user_id) < quota


async def ensure_ai_allowance(session: AsyncSession, user_id: int) -> None:
    if not await has_ai_allowance(session, user_id):
        raise HTTPException(
            status_code=429,
            detail="You've used today's AI allowance. It resets at midnight UTC.",
        )


def add_usage_event(session: AsyncSession, user_id: int, kind: str, usage: Usage) -> None:
    if usage.calls:
        session.add(UsageEvent(
            user_id=user_id, kind=kind,
            prompt_tokens=usage.prompt_tokens, completion_tokens=usage.completion_tokens,
        ))


async def storage_used(session: AsyncSession, user_id: int) -> tuple[int, int]:
    """(number of documents, bytes stored)"""
    count, size = (await session.execute(
        select(func.count(), func.coalesce(func.sum(Document.size_bytes), 0)).where(Document.user_id == user_id)
    )).one()
    return int(count), int(size)


async def ensure_storage_allowance(session: AsyncSession, user_id: int, incoming_bytes: int) -> None:
    settings = get_settings()
    count, size = await storage_used(session, user_id)
    if settings.max_documents_per_user > 0 and count >= settings.max_documents_per_user:
        raise HTTPException(
            status_code=403,
            detail=f"You've reached the limit of {settings.max_documents_per_user} documents. Delete some to upload more.",
        )
    limit = settings.max_storage_mb_per_user * 1024 * 1024
    if settings.max_storage_mb_per_user > 0 and size + incoming_bytes > limit:
        raise HTTPException(
            status_code=403,
            detail=f"This upload would exceed your {settings.max_storage_mb_per_user} MB of storage. Delete some documents first.",
        )


async def usage_summary(session: AsyncSession, user_id: int) -> dict:
    settings = get_settings()
    count, size = await storage_used(session, user_id)
    return {
        "documents": {"used": count, "limit": settings.max_documents_per_user or None},
        "storage_bytes": {"used": size, "limit": settings.max_storage_mb_per_user * 1024 * 1024 or None},
        "ai_tokens_today": {"used": await tokens_used_today(session, user_id), "limit": settings.daily_token_quota or None},
    }
