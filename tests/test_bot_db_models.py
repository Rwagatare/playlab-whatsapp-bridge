"""Tests for bot-related DB model fields (no DB session required)."""

import uuid

from app.db.models import Conversation, User


def test_user_active_bot_defaults_to_none():
    user = User(phone_hash="a" * 64)
    assert user.active_bot is None


def test_user_active_bot_settable():
    user = User(phone_hash="b" * 64, active_bot="ai-or-not")
    assert user.active_bot == "ai-or-not"


def test_user_active_bot_can_be_updated():
    user = User(phone_hash="c" * 64)
    user.active_bot = "teachable-machine"
    assert user.active_bot == "teachable-machine"


def test_conversation_bot_key_defaults_to_none():
    conv = Conversation(user_id=uuid.uuid4(), status="active")
    assert conv.bot_key is None


def test_conversation_bot_key_settable():
    conv = Conversation(user_id=uuid.uuid4(), status="active", bot_key="ai-or-not")
    assert conv.bot_key == "ai-or-not"


def test_conversation_bot_key_can_be_updated():
    conv = Conversation(user_id=uuid.uuid4(), status="active")
    conv.bot_key = "teachable-machine"
    assert conv.bot_key == "teachable-machine"
