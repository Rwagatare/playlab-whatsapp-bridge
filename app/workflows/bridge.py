import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.engine import get_session_or_none
from app.db.models import User
from app.parsers.turnio import parse_inbound as parse_turnio_inbound
from app.parsers.twilio import parse_inbound as parse_twilio_inbound
from app.privacy.pseudonymize import pseudonymize_user_id
from app.services.claude_service import ClaudeService
from app.services.playlab_service import PlaylabService
from app.services.turnio_service import TurnioService
from app.services.twilio_service import TwilioService
from app.schemas.inbound import InboundMessage

logger = logging.getLogger(__name__)


async def _ensure_user(session: AsyncSession, phone_hash: str) -> User:
    """Look up a user by phone_hash, or create one if they don't exist yet."""
    stmt = select(User).where(User.phone_hash == phone_hash)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        user = User(phone_hash=phone_hash)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info("Created new user for phone_hash=%s...", phone_hash[:8])
    return user


async def process_inbound_message(
    inbound: InboundMessage,
    settings: Settings,
) -> str:
    # Keep PII out of downstream processing.
    pseudonymous_user_id = pseudonymize_user_id(
        inbound.sender_id,
        settings.salt,
    )

    # Persist user if database is available (graceful degradation).
    async for session in get_session_or_none():
        if session is not None:
            try:
                await _ensure_user(session, pseudonymous_user_id)
            except Exception:
                logger.warning("DB write failed; continuing without persistence", exc_info=True)
        break

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


async def handle_inbound_message(payload: dict, settings: Settings) -> None:
    # Extract minimal fields and keep PII out of downstream processing.
    inbound = parse_turnio_inbound(payload)
    if not inbound:
        return

    response_text = await _safe_llm_response(inbound, settings)
    turnio_client = TurnioService(
        api_key=settings.turnio_api_key,
        base_url=settings.turnio_base_url,
        mock_mode=settings.mock_mode,
    )
    await turnio_client.send_text(to=inbound.sender_id, message=response_text)


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
