from dataclasses import dataclass


@dataclass(frozen=True)
class TurnioService:
    api_key: str
    base_url: str

    async def send_text(self, to: str, message: str) -> None:
        """Placeholder for Turn.io HTTP send; implement later."""
        _ = (to, message)
        return None
