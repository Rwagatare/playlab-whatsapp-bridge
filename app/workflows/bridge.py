from app.core.config import Settings
from app.privacy.pseudonymize import pseudonymize_user_id
from app.services.playlab_service import PlaylabService
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

    playlab_client = PlaylabService(
        api_key=settings.playlab_api_key,
        project_id=settings.playlab_project_id,
        base_url=settings.playlab_base_url,
    )
    turnio_client = TurnioClient(api_key=settings.turnio_api_key)

    _ = (image, pseudonymous_user_id)
    conversation_id = await playlab_client.create_conversation()
    response_text = await playlab_client.send_message(
        conversation_id=conversation_id,
        message=text or "",
    )
    await turnio_client.send_message(to=sender, text=response_text)
