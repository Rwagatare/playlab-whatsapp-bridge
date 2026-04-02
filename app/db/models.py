"""ORM models for the WhatsApp bridge.

Three tables:
  - users:         one row per unique phone_hash (pseudonymized phone number)
  - conversations: one row per chat session (a user can have many over time)
  - messages:      one row per message (user or assistant) within a conversation
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    # Return naive UTC datetime: our columns use TIMESTAMP WITHOUT TIME ZONE,
    # which expects tz-unaware values.  If columns ever switch to WITH TIME ZONE,
    # remove the .replace() call.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    # UUID primary key — avoids sequential ID enumeration.
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    # SHA-256 hex digest of the phone number (64 chars). Never store raw numbers.
    phone_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=_utcnow,
        server_default=text("now()"),
    )
    active_bot: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None,
    )

    # One user can have many conversations.
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    # Which user owns this conversation.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Playlab-side conversation ID (allows reusing the same Playlab conversation).
    external_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        default=None,
    )
    # Slug of the bot active when this conversation was created.
    bot_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None,
    )
    # "active" or "expired" — used for session timeout (#29).
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        server_default=text("'active'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=_utcnow,
        server_default=text("now()"),
    )
    # Updated on every new message — used to detect idle sessions.
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=_utcnow,
        server_default=text("now()"),
        onupdate=_utcnow,
    )

    user: Mapped["User"] = relationship(back_populates="conversations")
    # Messages come back in chronological order by default.
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    # Composite index: "find the active conversation for this user" — the main query.
    __table_args__ = (Index("ix_conversations_user_status", "user_id", "status"),)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    # Which conversation this message belongs to.
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    # "user" or "assistant" — matches Claude API convention.
    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=_utcnow,
        server_default=text("now()"),
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    # Index: "get messages for a conversation in order" — the multi-turn memory query.
    __table_args__ = (Index("ix_messages_conversation_created", "conversation_id", "created_at"),)
