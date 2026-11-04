from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.db.models import Conversation, Document, Message, User
from app.retrieval.answer import answer_question

settings = get_settings()
router = APIRouter(tags=["Chat"])


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=settings.max_question_chars)
    # Continue a conversation, or start one. A new conversation searches document_ids,
    # or every document when it is omitted.
    conversation_id: int | None = None
    document_ids: list[int] | None = Field(default=None, min_length=1, max_length=100)


def _title(question: str, limit: int = 80) -> str:
    question = " ".join(question.split())
    if len(question) <= limit:
        return question
    return question[:limit].rsplit(" ", 1)[0] + "…"


def serialize_message(message: Message) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "sources": message.sources or [],
        "abstained": message.abstained,
        "created_at": message.created_at,
    }


def serialize_conversation(conversation: Conversation) -> dict:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "document_ids": conversation.document_ids,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
    }


async def _get_owned_conversation(session: DbSession, conversation_id: int, user: User) -> Conversation:
    conversation = (await session.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )).scalars().first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


async def _new_conversation(session: DbSession, user: User, question: str, document_ids: list[int] | None) -> Conversation:
    if document_ids:
        document_ids = sorted(set(document_ids))
        owned = (await session.execute(
            select(func.count()).select_from(Document)
            .where(Document.user_id == user.id, Document.id.in_(document_ids))
        )).scalar()
        if owned != len(document_ids):
            raise HTTPException(status_code=404, detail="Document not found")
    conversation = Conversation(user_id=user.id, title=_title(question), document_ids=document_ids or None)
    session.add(conversation)
    await session.flush()
    return conversation


@router.post("/chat")
async def ask(request: AskRequest, user: CurrentUser, session: DbSession):
    if request.conversation_id is not None:
        conversation = await _get_owned_conversation(session, request.conversation_id, user)
    else:
        conversation = await _new_conversation(session, user, request.question, request.document_ids)

    recent = (await session.execute(
        select(Message.role, Message.content).where(Message.conversation_id == conversation.id)
        .order_by(Message.id.desc()).limit(settings.chat_history_messages)
    )).all()
    history = [{"role": r.role, "content": r.content} for r in reversed(recent)]

    answer = await answer_question(session, user.id, request.question, conversation.document_ids, history)

    session.add(Message(conversation_id=conversation.id, role="user", content=request.question))
    reply = Message(
        conversation_id=conversation.id, role="assistant", content=answer.text,
        sources=answer.sources_json(), abstained=answer.abstained,
    )
    session.add(reply)
    conversation.updated_at = func.now()
    await session.commit()
    await session.refresh(reply)
    await session.refresh(conversation)

    return {
        "conversation": serialize_conversation(conversation),
        "message": serialize_message(reply),
        "search_query": answer.search_query,
    }


@router.get("/conversations")
async def list_conversations(user: CurrentUser, session: DbSession):
    result = await session.execute(
        select(Conversation).where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc()).limit(200)
    )
    return [serialize_conversation(c) for c in result.scalars()]


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: int, user: CurrentUser, session: DbSession):
    conversation = await _get_owned_conversation(session, conversation_id, user)
    messages = (await session.execute(
        select(Message).where(Message.conversation_id == conversation.id).order_by(Message.id)
    )).scalars()
    return {**serialize_conversation(conversation), "messages": [serialize_message(m) for m in messages]}


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: int, user: CurrentUser, session: DbSession):
    conversation = await _get_owned_conversation(session, conversation_id, user)
    await session.delete(conversation)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
