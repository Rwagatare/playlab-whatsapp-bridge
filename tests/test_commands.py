"""Tests for app/commands/parser.py"""

import pytest

from app.commands.parser import CommandResult, CommandType, parse_command


# --- Plain messages return None ---

def test_plain_message_returns_none():
    assert parse_command("Hello there!") is None


def test_empty_string_returns_none():
    assert parse_command("") is None


def test_none_like_empty_returns_none():
    assert parse_command("   ") is None


# --- Unknown commands return None ---

def test_unknown_command_returns_none():
    assert parse_command("/unknown") is None


def test_bare_slash_returns_none():
    assert parse_command("/") is None


# --- /bots ---

def test_bots_command():
    result = parse_command("/bots")
    assert result == CommandResult(command=CommandType.BOTS, args=None)


def test_bots_command_uppercase():
    result = parse_command("/BOTS")
    assert result == CommandResult(command=CommandType.BOTS, args=None)


# --- /switch ---

def test_switch_with_slug():
    result = parse_command("/switch ai-or-not")
    assert result == CommandResult(command=CommandType.SWITCH, args="ai-or-not")


def test_switch_slug_normalized_to_lowercase():
    result = parse_command("/switch AI-OR-NOT")
    assert result == CommandResult(command=CommandType.SWITCH, args="ai-or-not")


def test_switch_mixed_case_command_and_slug():
    result = parse_command("/SWITCH Teachable-Machine")
    assert result == CommandResult(command=CommandType.SWITCH, args="teachable-machine")


def test_switch_without_slug():
    result = parse_command("/switch")
    assert result == CommandResult(command=CommandType.SWITCH, args=None)


# --- /current ---

def test_current_command():
    result = parse_command("/current")
    assert result == CommandResult(command=CommandType.CURRENT, args=None)


def test_current_command_uppercase():
    result = parse_command("/CURRENT")
    assert result == CommandResult(command=CommandType.CURRENT, args=None)


# --- /help ---

def test_help_command():
    result = parse_command("/help")
    assert result == CommandResult(command=CommandType.HELP, args=None)


def test_help_command_mixed_case():
    result = parse_command("/Help")
    assert result == CommandResult(command=CommandType.HELP, args=None)


# --- /reset ---

def test_reset_command():
    result = parse_command("/reset")
    assert result == CommandResult(command=CommandType.RESET, args=None)


def test_reset_command_uppercase():
    result = parse_command("/RESET")
    assert result == CommandResult(command=CommandType.RESET, args=None)


# --- Whitespace handling ---

def test_leading_whitespace_is_stripped():
    result = parse_command("  /bots  ")
    assert result == CommandResult(command=CommandType.BOTS, args=None)


def test_switch_with_extra_whitespace():
    result = parse_command("/switch   ai-or-not")
    assert result == CommandResult(command=CommandType.SWITCH, args="ai-or-not")
