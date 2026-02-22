import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.engine import get_session_or_none
from app.db.models import Conversation, User
from app.parsers.twilio import parse_inbound as parse_twilio_inbound
from app.privacy.pseudonymize import pseudonymize_user_id
from app.services.claude_service import ClaudeService
from app.services.playlab_service import PlaylabService
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


async def _lookup_conversation_in_db(
    session: AsyncSession,
    pseudonymous_user_id: str,
) -> str | None:
    """Find the most recent active Playlab conversation for this user in DB."""
    user_stmt = select(User).where(User.phone_hash == pseudonymous_user_id)
    user_result = await session.execute(user_stmt)
    user = user_result.scalar_one_or_none()
    if user is None:
        return None

    conv_stmt = (
        select(Conversation)
        .where(
            Conversation.user_id == user.id,
            Conversation.status == "active",
            Conversation.external_id.isnot(None),
        )
        .order_by(Conversation.updated_at.desc())
        .limit(1)
    )
    conv_result = await session.execute(conv_stmt)
    conv = conv_result.scalar_one_or_none()
    if conv and conv.external_id:
        return conv.external_id
    return None


async def process_inbound_message(
    inbound: InboundMessage,
    settings: Settings,
) -> str:
    # Keep PII out of downstream processing.
    pseudonymous_user_id = pseudonymize_user_id(
        inbound.sender_id,
        settings.salt,
    )

    message_text = inbound.text or ""

    if settings.llm_provider == "claude":
        # Persist user if database is available (graceful degradation).
        async for session in get_session_or_none():
            if session is not None:
                try:
                    await _ensure_user(session, pseudonymous_user_id)
                except Exception:
                    logger.warning("DB write failed; continuing without persistence", exc_info=True)
            break
        return await _call_claude(message_text, settings)

    # --- Playlab path: look up or create a conversation ---

    # 1. Look up existing conversation in DB.
    existing_conv_id: str | None = None
    async for session in get_session_or_none():
        if session is not None:
            try:
                await _ensure_user(session, pseudonymous_user_id)
                existing_conv_id = await _lookup_conversation_in_db(
                    session, pseudonymous_user_id,
                )
            except Exception:
                logger.warning("DB lookup failed", exc_info=True)
        break

    # 2. Call Playlab (reuse existing conversation or create new one).
    reply, used_conv_id, is_new = await _call_playlab(
        message=message_text,
        settings=settings,
        conversation_id=existing_conv_id,
    )

    # 3. If a new conversation was created, persist to DB.
    if is_new and used_conv_id:
        async for session in get_session_or_none():
            if session is not None:
                try:
                    user = await _ensure_user(session, pseudonymous_user_id)
                    conv = Conversation(
                        user_id=user.id,
                        external_id=used_conv_id,
                        status="active",
                    )
                    session.add(conv)
                    await session.commit()
                    logger.info(
                        "Saved conversation external_id=%s for user=%s...",
                        used_conv_id,
                        pseudonymous_user_id[:8],
                    )
                except Exception:
                    logger.warning("DB write for conversation failed", exc_info=True)
            break

    return reply


async def _call_playlab(
    message: str,
    settings: Settings,
    conversation_id: str | None = None,
) -> tuple[str, str, bool]:
    """Call Playlab API, reusing or creating a conversation.

    Returns (reply_text, conversation_id_used, is_new_conversation).
    """
    playlab_client = PlaylabService(
        api_key=settings.playlab_api_key,
        project_id=settings.playlab_project_id,
        base_url=settings.playlab_base_url,
        mock_mode=settings.mock_mode,
    )

    is_new = conversation_id is None
    if is_new:
        conversation_id = await playlab_client.create_conversation()
        logger.info("Created new Playlab conversation: %s", conversation_id)
    else:
        logger.info("Reusing Playlab conversation: %s", conversation_id)

    try:
        reply = await playlab_client.send_message(
            conversation_id=conversation_id,
            message=message,
        )
        return reply, conversation_id, is_new
    except Exception:
        if not is_new:
            # The existing conversation may have expired; create a fresh one.
            logger.warning(
                "send_message failed on existing conversation %s; creating new one",
                conversation_id,
                exc_info=True,
            )
            new_conversation_id = await playlab_client.create_conversation()
            logger.info("Created replacement Playlab conversation: %s", new_conversation_id)
            reply = await playlab_client.send_message(
                conversation_id=new_conversation_id,
                message=message,
            )
            return reply, new_conversation_id, True
        raise


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
