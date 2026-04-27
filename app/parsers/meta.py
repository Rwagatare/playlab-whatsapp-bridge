import logging

from app.schemas.inbound import InboundMessage

logger = logging.getLogger(__name__)


def parse_inbound(payload: dict) -> InboundMessage | None:
    """Extract sender and text from a Meta WhatsApp Cloud API webhook payload.

    Meta sends deeply nested JSON. A typical text message looks like:
        entry[0].changes[0].value.messages[0]

    Status updates (delivered/read) arrive in the same webhook but have
    a "statuses" key instead of "messages" — we skip those.
    """
    try:
        entry = payload.get("entry", [])
        if not entry:
            return None

        changes = entry[0].get("changes", [])
        if not changes:
            return None

        value = changes[0].get("value", {})

        # Status updates (delivered, read, etc.) — not an inbound message.
        messages = value.get("messages")
        if not messages:
            return None

        message = messages[0]
        sender = message.get("from")
        if not sender:
            # Fallback to contacts list.
            contacts = value.get("contacts", [])
            if contacts:
                sender = contacts[0].get("wa_id")

        if not sender:
            return None

        # Extract text body (only for text messages).
        msg_type = message.get("type", "")
        text = None
        image_url = None
        message_id: str | None = message.get("id") or None

        if msg_type == "text":
            text = message.get("text", {}).get("body")
        elif msg_type == "image":
            image_url = message.get("image", {}).get("link")

        # Cap message length to prevent abuse (WhatsApp max is ~65k chars).
        if text and len(text) > 10000:
            text = text[:10000]

        return InboundMessage(sender_id=sender, text=text, image_url=image_url, message_id=message_id)

    except (IndexError, KeyError, TypeError):
        logger.warning("Failed to parse Meta webhook payload", exc_info=True)
        return None
