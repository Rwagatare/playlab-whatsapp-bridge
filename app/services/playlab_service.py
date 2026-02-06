from dataclasses import dataclass

import httpx


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
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json={},
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise RuntimeError("Playlab conversation creation failed") from exc

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
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json=body,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError("Playlab message send failed") from exc

        content_type = response.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            payload = response.json()
            response_text = payload.get("response") or payload.get("message")
        else:
            response_text = response.text.strip()
        if not response_text:
            raise RuntimeError("Playlab response missing message text")
        return response_text
