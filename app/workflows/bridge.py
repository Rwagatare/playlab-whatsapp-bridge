import logging

from app.core.config import Settings
from app.parsers.twilio import parse_inbound as parse_twilio_inbound
from app.privacy.pseudonymize import pseudonymize_user_id
from app.services.claude_service import ClaudeService
from app.services.playlab_service import PlaylabService
from app.services.twilio_service import TwilioService
from app.schemas.inbound import InboundMessage

logger = logging.getLogger(__name__)


async def process_inbound_message(
    inbound: InboundMessage,
    settings: Settings,
) -> str:
    # Keep PII out of downstream processing.
    pseudonymous_user_id = pseudonymize_user_id(
        inbound.sender_id,
        settings.salt,
    )
    _ = (inbound.image_url, pseudonymous_user_id)

    message_text = inbound.text or ""

    if settings.llm_provider == "claude":
        return await _call_claude(message_text, settings)
    return await _call_playlab(message_text, settings)


async def _call_playlab(message: str, settings: Settings) -> str:
    playlab_client = PlaylabService(
        api_key=settings.playlab_api_key,
        project_id=settings.playlab_project_id,
        base_url=settings.playlab_base_url,
        mock_mode=settings.mock_mode,
    )
    conversation_id = await playlab_client.create_conversation()
    return await playlab_client.send_message(
        conversation_id=conversation_id,
        message=message,
    )


async def _call_claude(message: str, settings: Settings) -> str:
    claude_client = ClaudeService(
        api_key=settings.anthropic_api_key,
        model=settings.claude_model,
        system_prompt=settings.claude_system_prompt,
        mock_mode=settings.mock_mode,
    )
    return await claude_client.send_message(message)


async def _safe_llm_response(
    inbound: InboundMessage,
    settings: Settings,
) -> str:
    try:
        return await process_inbound_message(inbound, settings)
    except Exception as exc:
        logger.exception("LLM API failed (%s): %s", settings.llm_provider, exc)
        return "Sorry, the AI service is temporarily unavailable. Please try again."


async def handle_twilio_message(form_data: dict[str, str], settings: Settings) -> None:
    logger.info("Twilio webhook received: %s", list(form_data.keys()))
    inbound = parse_twilio_inbound(form_data)
    if not inbound:
        logger.warning("Could not parse Twilio inbound (missing From?)")
        return

    logger.info("Parsed inbound from %s: %s", inbound.sender_id, inbound.text[:50] if inbound.text else "(empty)")
    response_text = await _safe_llm_response(inbound, settings)
    logger.info("Response to send: %s", response_text[:100])

    twilio_client = TwilioService(
        account_sid=settings.twilio_account_sid,
        auth_token=settings.twilio_auth_token,
        whatsapp_number=settings.twilio_whatsapp_number,
        mock_mode=settings.mock_mode,
    )
    try:
        await twilio_client.send_text(to=inbound.sender_id, message=response_text)
        logger.info("Twilio send succeeded to %s", inbound.sender_id)
    except Exception as exc:
        logger.exception("Twilio send failed: %s", exc)
