from app.core.config import Settings
from app.parsers.turnio import parse_inbound
from app.privacy.pseudonymize import pseudonymize_user_id
from app.services.playlab_service import PlaylabService
from app.services.turnio import TurnioClient


async def handle_inbound_message(payload: dict, settings: Settings) -> None:
    # Extract minimal fields and keep PII out of downstream processing.
    inbound = parse_inbound(payload)
    if not inbound:
        return

    pseudonymous_user_id = pseudonymize_user_id(
        inbound.sender_id,
        settings.salt,
    )

    playlab_client = PlaylabService(
        api_key=settings.playlab_api_key,
        project_id=settings.playlab_project_id,
        base_url=settings.playlab_base_url,
    )
    turnio_client = TurnioClient(api_key=settings.turnio_api_key)

    _ = (inbound.image_url, pseudonymous_user_id)
    conversation_id = await playlab_client.create_conversation()
    response_text = await playlab_client.send_message(
        conversation_id=conversation_id,
        message=inbound.text or "",
    )
    await turnio_client.send_message(to=inbound.sender_id, text=response_text)
