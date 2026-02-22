import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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
        import httpx
        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{self.account_sid}/Messages.json"
        )
        data = {
            "To": to,
            "From": self.whatsapp_number,
            "Body": message,
        }
        logger.info("Twilio send: To=%s From=%s Body=%s", to, self.whatsapp_number, message[:120])
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, data=data, auth=self._auth())
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text if exc.response is not None else ""
            raise RuntimeError(
                f"Twilio message send failed: status={exc.response.status_code} body={body[:500]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Twilio message send failed: {exc}") from exc
