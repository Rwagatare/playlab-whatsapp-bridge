from app.schemas.inbound import InboundMessage


def parse_inbound(form_data: dict[str, str]) -> InboundMessage | None:
    """Extract sender and text from Twilio WhatsApp webhook form data."""
    sender = form_data.get("From")
    message = form_data.get("Body")

    if not sender:
        return None

    # Cap message length to prevent abuse (WhatsApp max is ~65k chars).
    if message and len(message) > 10000:
        message = message[:10000]

    return InboundMessage(sender_id=sender, text=message, image_url=None)
