"""Tests for app/core/bot_registry.py"""

import pytest

from app.core.bot_registry import (
    BotConfig,
    get_bot_by_slug,
    get_default_bot,
    parse_bot_registry,
)


def test_parse_empty_string():
    assert parse_bot_registry("") == []


def test_parse_two_valid_entries():
    result = parse_bot_registry(
        "AI or Not:ai-or-not:cmd3j9ksa0x03er0u7k9m0pgl,"
        "Teachable Machine:teachable-machine:cmddeyhyz0j5rl30uq97hw6mg"
    )
    assert len(result) == 2
    assert result[0] == BotConfig(
        display_name="AI or Not",
        slug="ai-or-not",
        project_id="cmd3j9ksa0x03er0u7k9m0pgl",
    )
    assert result[1] == BotConfig(
        display_name="Teachable Machine",
        slug="teachable-machine",
        project_id="cmddeyhyz0j5rl30uq97hw6mg",
    )


def test_parse_malformed_entries_skipped():
    result = parse_bot_registry(
        "Valid Bot:valid-bot:proj123,"
        "bad-entry,"           # only 1 part
        ":missing-name:proj,"  # empty display name
        "no-project:np:,"      # empty project_id
        "Extra:a:b:c,"         # 4 parts (too many)
    )
    assert len(result) == 1
    assert result[0].slug == "valid-bot"


def test_parse_real_example_string():
    env = "AI or Not:ai-or-not:cmd3j9ksa0x03er0u7k9m0pgl,Teachable Machine:teachable-machine:cmddeyhyz0j5rl30uq97hw6mg"
    result = parse_bot_registry(env)
    assert len(result) == 2
    assert result[0].display_name == "AI or Not"
    assert result[1].display_name == "Teachable Machine"


def test_get_bot_by_slug_found():
    registry = parse_bot_registry(
        "AI or Not:ai-or-not:proj1,Teachable Machine:teachable-machine:proj2"
    )
    bot = get_bot_by_slug(registry, "teachable-machine")
    assert bot is not None
    assert bot.display_name == "Teachable Machine"
    assert bot.project_id == "proj2"


def test_get_bot_by_slug_not_found():
    registry = parse_bot_registry("AI or Not:ai-or-not:proj1")
    assert get_bot_by_slug(registry, "nonexistent") is None


def test_get_bot_by_slug_empty_registry():
    assert get_bot_by_slug([], "any-slug") is None


def test_get_default_bot_returns_first():
    registry = parse_bot_registry(
        "AI or Not:ai-or-not:proj1,Teachable Machine:teachable-machine:proj2"
    )
    bot = get_default_bot(registry)
    assert bot is not None
    assert bot.slug == "ai-or-not"


def test_get_default_bot_empty_registry():
    assert get_default_bot([]) is None
