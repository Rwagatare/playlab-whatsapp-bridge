import logging
from dataclasses import dataclass

import httpx

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
        if content_type.startswith("application/json"):
            payload = response.json()
            response_text = payload.get("response") or payload.get("message")
        else:
            response_text = response.text.strip()
        if not response_text:
            raise RuntimeError("Playlab response missing message text")
        return response_text
