from dataclasses import dataclass


@dataclass(frozen=True)
class PlaylabClient:
    api_key: str

    async def send_message(
        self,
        app_id: str,
        message_text: str | None,
        image_url: str | None,
        user_id: str,
    ) -> str:
        """Placeholder for Playlab API call; returns stub response."""
        _ = (app_id, message_text, image_url, user_id)
        return "Playlab response placeholder"
