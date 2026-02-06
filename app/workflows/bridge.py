from app.core.config import Settings
from app.parsers.turnio import parse_inbound as parse_turnio_inbound
from app.parsers.twilio import parse_inbound as parse_twilio_inbound
from app.privacy.pseudonymize import pseudonymize_user_id
from app.services.playlab_service import PlaylabService
from app.services.turnio_service import TurnioService
from app.services.twilio_service import TwilioService
from app.schemas.inbound import InboundMessage


async def process_inbound_message(
    inbound: InboundMessage,
    settings: Settings,
) -> str:
    # Keep PII out of downstream processing.
    pseudonymous_user_id = pseudonymize_user_id(
        inbound.sender_id,
        settings.salt,
    )

    playlab_client = PlaylabService(
        api_key=settings.playlab_api_key,
        project_id=settings.playlab_project_id,
        base_url=settings.playlab_base_url,
        mock_mode=settings.mock_mode,
    )
    _ = (inbound.image_url, pseudonymous_user_id)
    conversation_id = await playlab_client.create_conversation()
    response_text = await playlab_client.send_message(
        conversation_id=conversation_id,
        message=inbound.text or "",
    )
    return response_text


async def handle_inbound_message(payload: dict, settings: Settings) -> None:
    # Extract minimal fields and keep PII out of downstream processing.
    inbound = parse_turnio_inbound(payload)
    if not inbound:
        return

    response_text = await process_inbound_message(inbound, settings)
    turnio_client = TurnioService(
        api_key=settings.turnio_api_key,
        base_url=settings.turnio_base_url,
        mock_mode=settings.mock_mode,
    )
    await turnio_client.send_text(to=inbound.sender_id, message=response_text)


async def handle_twilio_message(form_data: dict[str, str], settings: Settings) -> None:
    inbound = parse_twilio_inbound(form_data)
    if not inbound:
        return

    response_text = await process_inbound_message(inbound, settings)
    twilio_client = TwilioService(
        account_sid=settings.twilio_account_sid,
        auth_token=settings.twilio_auth_token,
        whatsapp_number=settings.twilio_whatsapp_number,
        mock_mode=settings.mock_mode,
    )
    await twilio_client.send_text(to=inbound.sender_id, message=response_text)
