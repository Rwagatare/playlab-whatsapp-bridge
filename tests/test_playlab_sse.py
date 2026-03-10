"""Tests for Playlab SSE parsing (_extract_text_from_sse, _looks_like_sse)."""

from app.services.playlab_service import _extract_text_from_sse, _looks_like_sse


class TestLooksLikeSse:
    def test_event_prefix(self):
        assert _looks_like_sse("some header\nevent: message\ndata: {}") is True

    def test_starts_with_event(self):
        assert _looks_like_sse("event: message\ndata: {}") is True

    def test_data_prefix(self):
        assert _looks_like_sse("some header\ndata: {}") is True

    def test_plain_json(self):
        assert _looks_like_sse('{"response": "hello"}') is False

    def test_empty_string(self):
        assert _looks_like_sse("") is False


class TestExtractTextFromSse:
    def test_single_segment(self):
        raw = (
            "event: message\n"
            'data: {"source": "provider", "id": "1"}\n'
            "\n"
            "event: append\n"
            'data: {"delta": "Hello "}\n'
            "\n"
            "event: append\n"
            'data: {"delta": "world!"}\n'
        )
        assert _extract_text_from_sse(raw) == "Hello world!"

    def test_multi_segment_returns_last(self):
        """When tool calls split the response, return only the final segment."""
        raw = (
            "event: message\n"
            'data: {"source": "provider", "id": "1"}\n'
            "\n"
            "event: append\n"
            'data: {"delta": "Let me look that up."}\n'
            "\n"
            "event: tool_call\n"
            'data: {"name": "search", "args": {}}\n'
            "\n"
            "event: tool_result\n"
            'data: {"result": "42"}\n'
            "\n"
            "event: message\n"
            'data: {"source": "provider", "id": "2"}\n'
            "\n"
            "event: append\n"
            'data: {"delta": "The answer "}\n'
            "\n"
            "event: append\n"
            'data: {"delta": "is 42."}\n'
        )
        assert _extract_text_from_sse(raw) == "The answer is 42."

    def test_malformed_json_skipped(self):
        raw = (
            "event: message\n"
            'data: {"source": "provider", "id": "1"}\n'
            "\n"
            "event: append\n"
            "data: not-json\n"
            "\n"
            "event: append\n"
            'data: {"delta": "valid"}\n'
        )
        assert _extract_text_from_sse(raw) == "valid"

    def test_empty_input_returns_empty(self):
        assert _extract_text_from_sse("") == ""

    def test_no_append_events_returns_raw(self):
        raw = 'event: message\ndata: {"source": "provider", "id": "1"}\n'
        # No append events → no segments → falls back to raw.strip()
        result = _extract_text_from_sse(raw)
        assert result == raw.strip()

    def test_non_provider_message_ignored(self):
        """Messages from non-provider sources don't start new segments."""
        raw = (
            "event: message\n"
            'data: {"source": "user", "id": "1"}\n'
            "\n"
            "event: message\n"
            'data: {"source": "provider", "id": "2"}\n'
            "\n"
            "event: append\n"
            'data: {"delta": "response"}\n'
        )
        assert _extract_text_from_sse(raw) == "response"

    def test_whitespace_trimmed(self):
        raw = (
            "event: message\n"
            'data: {"source": "provider", "id": "1"}\n'
            "\n"
            "event: append\n"
            'data: {"delta": "  hello  "}\n'
        )
        assert _extract_text_from_sse(raw) == "hello"

    def test_empty_deltas_ignored(self):
        raw = (
            "event: message\n"
            'data: {"source": "provider", "id": "1"}\n'
            "\n"
            "event: append\n"
            'data: {"delta": ""}\n'
            "\n"
            "event: append\n"
            'data: {"delta": "content"}\n'
        )
        assert _extract_text_from_sse(raw) == "content"
