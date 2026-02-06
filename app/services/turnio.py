from dataclasses import dataclass


@dataclass(frozen=True)
class TurnioClient:
    api_key: str

    async def send_message(self, to: str, text: str) -> None:
        """Placeholder for Turn.io send; implement HTTP call later."""
        _ = (to, text)
        return None
