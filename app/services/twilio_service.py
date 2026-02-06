from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class TwilioService:
    account_sid: str
    auth_token: str
    whatsapp_number: str
    mock_mode: bool = False

    def _auth(self) -> tuple[str, str]:
        return self.account_sid, self.auth_token

    async def send_text(self, to: str, message: str) -> None:
        """Send a WhatsApp message via Twilio."""
        if self.mock_mode:
            return None
        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{self.account_sid}/Messages.json"
        )
        data = {
            "To": to,
            "From": self.whatsapp_number,
            "Body": message,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, data=data, auth=self._auth())
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError("Twilio message send failed") from exc
