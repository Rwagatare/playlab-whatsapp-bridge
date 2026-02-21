import json
import logging
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
        raw_text = response.text
        if content_type.startswith("application/json"):
            payload = response.json()
            response_text = payload.get("response") or payload.get("message")
        elif "text/event-stream" in content_type or self._looks_like_sse(raw_text):
            response_text = self._parse_sse(raw_text)
        else:
            response_text = raw_text.strip()
        if not response_text:
            raise RuntimeError("Playlab response missing message text")
        return response_text

    @staticmethod
    def _looks_like_sse(text: str) -> bool:
        """Detect SSE format by checking for event/data line patterns."""
        return "\nevent:" in text or text.startswith("event:") or "\ndata:" in text

    @staticmethod
    def _parse_sse(raw: str) -> str:
        """Extract and concatenate delta values from an SSE stream.

        Playlab returns events like:
            event: append
            data: {"delta": "Hello"}
        We collect all deltas from 'append' events into the final text.
        """
        chunks: list[str] = []
        current_event = ""
        for line in raw.splitlines():
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and current_event == "append":
                data_str = line.split(":", 1)[1].strip()
                try:
                    data = json.loads(data_str)
                    delta = data.get("delta", "")
                    if delta:
                        chunks.append(delta)
                except json.JSONDecodeError:
                    logger.warning("SSE: could not parse data line: %s", data_str)
        return "".join(chunks)
