from app.schemas.inbound import InboundMessage


def parse_inbound(payload: dict) -> InboundMessage | None:
    """Extract sender, text, and image URL from a Turn.io webhook payload."""
    messages = payload.get("messages") or []
    message = messages[0] if messages else {}

    sender = message.get("from")
    text = message.get("text", {}).get("body")
    image_url = message.get("image", {}).get("link")

    contacts = payload.get("contacts") or []
    if contacts and not sender:
        sender = contacts[0].get("wa_id")

    if not sender:
        return None

    return InboundMessage(sender_id=sender, text=text, image_url=image_url)
