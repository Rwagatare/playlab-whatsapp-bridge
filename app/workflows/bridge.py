from app.core.config import Settings
from app.privacy.pseudonymize import pseudonymize_user_id
from app.services.playlab import PlaylabClient
from app.services.turnio import TurnioClient


def _extract_inbound(payload: dict) -> tuple[str | None, str | None, str | None]:
    messages = payload.get("messages") or []
    message = messages[0] if messages else {}
    sender = message.get("from")
    text = message.get("text", {}).get("body")
    image = message.get("image", {}).get("link")

    contacts = payload.get("contacts") or []
    if contacts and not sender:
        sender = contacts[0].get("wa_id")

    return sender, text, image


async def handle_inbound_message(payload: dict, settings: Settings) -> None:
    # Extract minimal fields and keep PII out of downstream processing.
    sender, text, image = _extract_inbound(payload)
    if not sender:
        return

    pseudonymous_user_id = pseudonymize_user_id(sender, settings.salt)

    playlab_client = PlaylabClient(api_key=settings.playlab_api_key)
    turnio_client = TurnioClient(api_key=settings.turnio_api_key)

    response_text = await playlab_client.send_message(
        app_id="placeholder-app",
        message_text=text,
        image_url=image,
        user_id=pseudonymous_user_id,
    )
    await turnio_client.send_message(to=sender, text=response_text)
