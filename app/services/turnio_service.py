from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class TurnioService:
    api_key: str
    base_url: str
    mock_mode: bool = False

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def send_text(self, to: str, message: str) -> None:
        """Send a text message via Turn.io."""
        if self.mock_mode:
            return None
        url = f"{self.base_url}/v1/messages"
        payload = {"to": to, "type": "text", "text": {"body": message}}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    headers=self._headers(),
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError("Turn.io message send failed") from exc
