"""Tests for database models (User, Conversation, Message).

These run against an in-memory SQLite database — no PostgreSQL needed.
"""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message, User

pytestmark = pytest.mark.asyncio


async def test_create_user(db_session: AsyncSession) -> None:
    """A User row can be created with a phone_hash."""
    user = User(phone_hash="a" * 64)
    db_session.add(user)
    await db_session.flush()

    assert user.id is not None
    assert isinstance(user.id, uuid.UUID)
    assert user.phone_hash == "a" * 64
    assert isinstance(user.created_at, datetime)


async def test_create_conversation(db_session: AsyncSession) -> None:
    """A Conversation is linked to a User and defaults to active."""
    user = User(phone_hash="c" * 64)
    db_session.add(user)
    await db_session.flush()

    conv = Conversation(user_id=user.id)
    db_session.add(conv)
    await db_session.flush()

    assert conv.id is not None
    assert conv.status == "active"
    assert conv.user_id == user.id


async def test_create_message(db_session: AsyncSession) -> None:
    """A Message can be created and linked to a Conversation."""
    user = User(phone_hash="d" * 64)
    db_session.add(user)
    await db_session.flush()

    conv = Conversation(user_id=user.id)
    db_session.add(conv)
    await db_session.flush()

    msg = Message(conversation_id=conv.id, role="user", content="hello")
    db_session.add(msg)
    await db_session.flush()

    assert msg.id is not None
    assert msg.role == "user"
    assert msg.content == "hello"


async def test_conversation_messages_relationship(db_session: AsyncSession) -> None:
    """Messages are accessible via Conversation.messages."""
    user = User(phone_hash="e" * 64)
    db_session.add(user)
    await db_session.flush()

    conv = Conversation(user_id=user.id)
    db_session.add(conv)
    await db_session.flush()

    msg1 = Message(conversation_id=conv.id, role="user", content="hi")
    msg2 = Message(conversation_id=conv.id, role="assistant", content="hello!")
    db_session.add_all([msg1, msg2])
    await db_session.flush()

    await db_session.refresh(conv, ["messages"])
    assert len(conv.messages) == 2
    assert conv.messages[0].role == "user"
    assert conv.messages[1].role == "assistant"


async def test_lookup_user_by_phone_hash(db_session: AsyncSession) -> None:
    """Users can be queried by phone_hash."""
    user = User(phone_hash="ab" * 32)
    db_session.add(user)
    await db_session.flush()

    stmt = select(User).where(User.phone_hash == "ab" * 32)
    result = await db_session.execute(stmt)
    found = result.scalar_one_or_none()

    assert found is not None
    assert found.id == user.id
