import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Meta Graph API version — update when Meta releases new versions.
META_API_VERSION = "v21.0"


@dataclass(frozen=True)
class MetaService:
    """Send WhatsApp messages via the Meta Cloud API (Graph API)."""

    access_token: str
    phone_number_id: str
    mock_mode: bool = False

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def send_text(self, to: str, message: str) -> None:
        """Send a text message to a WhatsApp user.

        Args:
            to: Recipient phone number in E.164 format (digits only, e.g. "27123456789").
            message: The text message body (up to 4096 characters).
        """
        if self.mock_mode:
            logger.info("Meta mock send: dispatching message")
            return None
        import httpx

        url = f"https://graph.facebook.com/{META_API_VERSION}/{self.phone_number_id}/messages"
        body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": message},
        }
        logger.info("Meta send: dispatching message")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=body, headers=self._headers())
                logger.info(
                    "Meta send response: status=%s body=%s",
                    response.status_code,
                    response.text[:500],
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            resp_body = exc.response.text if exc.response is not None else ""
            raise RuntimeError(
                f"Meta message send failed: status={exc.response.status_code}"
                f" body={resp_body[:500]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Meta message send failed: {exc}") from exc
