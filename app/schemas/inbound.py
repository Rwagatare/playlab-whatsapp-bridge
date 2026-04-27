from dataclasses import dataclass


@dataclass(frozen=True)
class InboundMessage:
    sender_id: str
    text: str | None
    image_url: str | None
    message_id: str | None = None
