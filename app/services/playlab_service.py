import json
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlaylabService:
    api_key: str
    project_id: str
    base_url: str
    mock_mode: bool = False

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def create_conversation(self) -> str:
        if self.mock_mode:
            return "mock-conversation"
        import httpx
        url = f"{self.base_url}/projects/{self.project_id}/conversations"
        logger.info("Playlab create_conversation: POST %s", url)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json={},
                )
                logger.info(
                    "Playlab create_conversation response: status=%s body=%s",
                    response.status_code,
                    response.text[:500],
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Playlab conversation creation failed: {exc}"
            ) from exc

        conversation_id = payload.get("conversation", {}).get("id")
        if not conversation_id:
            raise RuntimeError("Playlab response missing conversation_id")
        return conversation_id

    async def send_message(self, conversation_id: str, message: str) -> str:
        if self.mock_mode:
            return f"Mock response: {message}"
        import httpx
        url = (
            f"{self.base_url}/projects/{self.project_id}"
            f"/conversations/{conversation_id}/messages"
        )
        body = {"input": {"message": message}}
        logger.info("Playlab send_message: POST %s", url)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json=body,
                )
                logger.info(
                    "Playlab send_message response: status=%s body=%s",
                    response.status_code,
                    response.text[:500],
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Playlab message send failed: {exc}") from exc

        content_type = response.headers.get("content-type", "")
        logger.info("Playlab response content-type: %s", content_type)
        raw = response.text
        if content_type.startswith("application/json"):
            payload = response.json()
            response_text = payload.get("response") or payload.get("message")
        elif "text/event-stream" in content_type or _looks_like_sse(raw):
            response_text = _extract_text_from_sse(raw)
        else:
            response_text = raw.strip()
        if not response_text:
            raise RuntimeError("Playlab response missing message text")
        # WhatsApp uses single * for bold; convert Markdown **bold** to *bold*.
        response_text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", response_text)
        return response_text


def _looks_like_sse(raw: str) -> bool:
    """Heuristic: detect SSE content even when Content-Type header doesn't say so."""
    return "\nevent:" in raw or raw.startswith("event:") or "\ndata:" in raw


def _extract_text_from_sse(raw: str) -> str:
    """Extract the final assistant message from Playlab SSE responses.

    Playlab streams a sequence of events. A typical multi-turn flow:
      1. event: message  (provider starts first message)
      2. event: append   (deltas for first message)
      3. event: tool_call / tool_result  (tool usage)
      4. event: message  (provider starts second message)
      5. event: append   (deltas for second message)

    We split on ``message`` events to isolate segments, then return only
    the text from the **last** segment (the final answer after all tool calls).
    """
    current_event: str | None = None
    # Each "message" event from the provider starts a new segment.
    # We collect deltas per segment and return only the last one.
    segments: list[list[str]] = []
    current_deltas: list[str] = []

    for line in raw.splitlines():
        if not line.strip():
            current_event = None
            continue
        if line.startswith("event:"):
            current_event = line[len("event:") :].strip()
            logger.debug("SSE event: %s", current_event)
            continue
        if not line.startswith("data:"):
            continue

        data_str = line[len("data:") :].strip()
        try:
            payload = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        if current_event == "message":
            source = payload.get("source", "")
            logger.debug("SSE message segment: source=%s id=%s", source, payload.get("id", ""))
            if source == "provider":
                # Start a new segment; save any previous deltas.
                if current_deltas:
                    segments.append(current_deltas)
                current_deltas = []
        elif current_event == "append":
            delta = payload.get("delta", "")
            if delta:
                current_deltas.append(delta)
        else:
            # Log non-append/message events (tool_call, tool_result, etc.)
            logger.debug("SSE event=%s data_keys=%s", current_event, list(payload.keys()))

    # Save the final segment.
    if current_deltas:
        segments.append(current_deltas)

    logger.info("SSE parsed %d message segment(s)", len(segments))
    for i, seg in enumerate(segments):
        text = "".join(seg).strip()
        logger.debug("  segment %d (%d chars): %s", i, len(text), text[:120])

    # Return the last segment (final answer after tool calls).
    if segments:
        return "".join(segments[-1]).strip()
    return raw.strip()
