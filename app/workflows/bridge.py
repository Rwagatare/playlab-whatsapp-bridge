import asyncio
import logging
import time

from app.commands.parser import CommandType, parse_command
from app.core.bot_registry import BotConfig, get_bot_by_slug, get_default_bot
from app.core.config import Settings
from app.parsers.twilio import parse_inbound as parse_twilio_inbound
from app.privacy.pseudonymize import pseudonymize_user_id
from app.schemas.inbound import InboundMessage
from app.services.claude_service import ClaudeService
from app.services.playlab_service import PlaylabService
from app.services.twilio_service import TwilioService

logger = logging.getLogger(__name__)

# In-memory fallback for active bot per user when DB is unavailable.
_active_bots_fallback: dict[str, str] = {}

# Debounce: tracks the latest message arrival time per user (monotonic clock).
_last_seen: dict[str, float] = {}


async def _ensure_user(session, phone_hash: str):
    """Look up a user by phone_hash, or create one if they don't exist yet."""
    from sqlalchemy import select

    from app.db.models import User

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


async def _lookup_conversation_for_user(
    session, user_id: int, bot_key: str | None = None
) -> str | None:
    """Find the most recent active Playlab conversation for a user by user_id."""
    from sqlalchemy import select

    from app.db.models import Conversation

    conditions = [
        Conversation.user_id == user_id,
        Conversation.status == "active",
        Conversation.external_id.isnot(None),
    ]
    if bot_key is not None:
        conditions.append(Conversation.bot_key == bot_key)

    conv_stmt = (
        select(Conversation)
        .where(*conditions)
        .order_by(Conversation.updated_at.desc())
        .limit(1)
    )
    conv_result = await session.execute(conv_stmt)
    conv = conv_result.scalar_one_or_none()
    if conv and conv.external_id:
        return conv.external_id
    return None


async def _expire_conversation_by_external_id(session, external_id: str) -> None:
    """Mark a conversation as expired by its Playlab external_id."""
    from sqlalchemy import update

    from app.db.models import Conversation

    stmt = (
        update(Conversation)
        .where(
            Conversation.external_id == external_id,
            Conversation.status == "active",
        )
        .values(status="expired")
    )
    await session.execute(stmt)


def _resolve_bot(active_bot_slug: str | None, settings: Settings) -> BotConfig:
    """Resolve BotConfig from slug or fall back to registry default or legacy setting."""
    registry = settings.playlab_bots
    if active_bot_slug and registry:
        bot = get_bot_by_slug(registry, active_bot_slug)
        if bot:
            return bot
    if registry:
        default = get_default_bot(registry)
        if default:
            return default
    # Synthesize from legacy single-project settings.
    return BotConfig(
        display_name="Default",
        slug="default",
        project_id=settings.playlab_project_id,
    )


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
        # get_session_or_none() is an async generator; we iterate once then
        # break to get either a session or None without holding it open.
        from app.db.engine import get_session_or_none

        async for session in get_session_or_none():
            if session is not None:
                try:
                    await _ensure_user(session, pseudonymous_user_id)
                except Exception:
                    logger.warning("DB write failed; continuing without persistence", exc_info=True)
            break
        return await _call_claude(message_text, settings)

    # --- Playlab path: look up or create a conversation ---
    from app.db.engine import get_session_or_none

    # Phase 1: DB lookup — ensure user exists and find active conversation.
    existing_conv_id: str | None = None
    user_id: int | None = None
    active_bot_slug: str | None = _active_bots_fallback.get(pseudonymous_user_id)
    async for session in get_session_or_none():
        if session is not None:
            try:
                user = await _ensure_user(session, pseudonymous_user_id)
                user_id = user.id
                active_bot_slug = user.active_bot or active_bot_slug
                existing_conv_id = await _lookup_conversation_for_user(
                    session, user_id, bot_key=active_bot_slug
                )
            except Exception:
                logger.warning("DB lookup failed", exc_info=True)
        break

    # Resolve which bot (and project_id) to use.
    bot = _resolve_bot(active_bot_slug, settings)

    # Phase 2: Call Playlab (reuse existing conversation or create new one).
    reply, used_conv_id, is_new = await _call_playlab(
        message=message_text,
        settings=settings,
        project_id=bot.project_id,
        conversation_id=existing_conv_id,
    )

    # Phase 3: Persist new conversation / expire stale one.
    if is_new and used_conv_id:
        async for session in get_session_or_none():
            if session is not None:
                try:
                    from app.db.models import Conversation

                    # If we had an old conversation that was replaced, expire it.
                    if existing_conv_id:
                        await _expire_conversation_by_external_id(session, existing_conv_id)

                    # Re-fetch user_id if the first session failed.
                    if user_id is None:
                        user = await _ensure_user(session, pseudonymous_user_id)
                        user_id = user.id

                    conv = Conversation(
                        user_id=user_id,
                        external_id=used_conv_id,
                        status="active",
                        bot_key=active_bot_slug,
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
    project_id: str,
    conversation_id: str | None = None,
) -> tuple[str, str, bool]:
    """Call Playlab API, reusing or creating a conversation.

    Returns (reply_text, conversation_id_used, is_new_conversation).
    """
    playlab_client = PlaylabService(
        api_key=settings.playlab_api_key,
        project_id=project_id,
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


async def _handle_reset(sender_id: str, settings: Settings) -> str:
    """Expire all active conversations for a user so the next message starts fresh."""
    from sqlalchemy import select, update

    from app.db.engine import get_session_or_none
    from app.db.models import Conversation, User

    phone_hash = pseudonymize_user_id(sender_id, settings.salt)
    expired_count = 0

    async for session in get_session_or_none():
        if session is not None:
            try:
                user_stmt = select(User).where(User.phone_hash == phone_hash)
                user = (await session.execute(user_stmt)).scalar_one_or_none()
                if user is not None:
                    stmt = (
                        update(Conversation)
                        .where(
                            Conversation.user_id == user.id,
                            Conversation.status == "active",
                        )
                        .values(status="expired")
                    )
                    result = await session.execute(stmt)
                    expired_count = result.rowcount
                    await session.commit()
                    logger.info(
                        "Reset: expired %d conversation(s) for user=%s...",
                        expired_count,
                        phone_hash[:8],
                    )
            except Exception:
                logger.warning("Reset: DB update failed", exc_info=True)
        break

    return "Your conversation history has been cleared. Feel free to start a new conversation!"


async def _handle_bots(settings: Settings) -> str:
    """List available bots with their switch commands."""
    registry = settings.playlab_bots
    if not registry:
        return "No bots are configured. Please ask your administrator to set PLAYLAB_BOTS."
    lines = ["Available bots:"]
    for bot in registry:
        lines.append(f"  {bot.display_name} — /switch {bot.slug}")
    return "\n".join(lines)


async def _handle_current(sender_id: str, settings: Settings) -> str:
    """Show the currently active bot for this user."""
    phone_hash = pseudonymize_user_id(sender_id, settings.salt)
    active_bot_slug: str | None = _active_bots_fallback.get(phone_hash)

    from app.db.engine import get_session_or_none
    from sqlalchemy import select

    async for session in get_session_or_none():
        if session is not None:
            try:
                from app.db.models import User
                user_stmt = select(User).where(User.phone_hash == phone_hash)
                user = (await session.execute(user_stmt)).scalar_one_or_none()
                if user is not None and user.active_bot:
                    active_bot_slug = user.active_bot
            except Exception:
                logger.warning("_handle_current: DB lookup failed", exc_info=True)
        break

    bot = _resolve_bot(active_bot_slug, settings)
    return f"Current bot: {bot.display_name}"


async def _handle_switch(sender_id: str, slug: str | None, settings: Settings) -> str:
    """Switch the active bot for this user."""
    if not slug:
        return "Usage: /switch <slug>\nSend /bots to see available bots."

    registry = settings.playlab_bots
    if not registry:
        return "No bots are configured. Please ask your administrator to set PLAYLAB_BOTS."

    bot = get_bot_by_slug(registry, slug)
    if bot is None:
        available = ", ".join(b.slug for b in registry)
        return f"Unknown bot '{slug}'. Available: {available}"

    phone_hash = pseudonymize_user_id(sender_id, settings.salt)

    from app.db.engine import get_session_or_none

    switched_in_db = False
    async for session in get_session_or_none():
        if session is not None:
            try:
                from sqlalchemy import select, update

                from app.db.models import Conversation, User

                user_stmt = select(User).where(User.phone_hash == phone_hash)
                user = (await session.execute(user_stmt)).scalar_one_or_none()
                if user is None:
                    user = User(phone_hash=phone_hash)
                    session.add(user)
                    await session.flush()
                    await session.refresh(user)

                # Expire all active conversations so the next message starts fresh.
                expire_stmt = (
                    update(Conversation)
                    .where(
                        Conversation.user_id == user.id,
                        Conversation.status == "active",
                    )
                    .values(status="expired")
                )
                await session.execute(expire_stmt)

                user.active_bot = slug
                await session.commit()
                switched_in_db = True
                logger.info(
                    "Switched user=%s... to bot=%s", phone_hash[:8], slug
                )
            except Exception:
                logger.warning("_handle_switch: DB update failed", exc_info=True)
        break

    if not switched_in_db:
        # Fallback: remember in-process dict.
        _active_bots_fallback[phone_hash] = slug

    return f"Switched to {bot.display_name}. Your next message will use this bot."


async def _handle_help() -> str:
    """List all available commands."""
    return (
        "Available commands:\n"
        "  /bots — list available bots\n"
        "  /switch <slug> — switch to a different bot\n"
        "  /current — show active bot\n"
        "  /reset — clear conversation history\n"
        "  /help — show this message"
    )


async def _process_and_reply(inbound: InboundMessage, settings: Settings) -> str:
    """Shared logic: dispatch commands or get LLM response."""
    cmd = parse_command(inbound.text or "")
    if cmd is None:
        return await _safe_llm_response(inbound, settings)
    if cmd.command == CommandType.RESET:
        return await _handle_reset(inbound.sender_id, settings)
    if cmd.command == CommandType.BOTS:
        return await _handle_bots(settings)
    if cmd.command == CommandType.CURRENT:
        return await _handle_current(inbound.sender_id, settings)
    if cmd.command == CommandType.SWITCH:
        return await _handle_switch(inbound.sender_id, cmd.args, settings)
    if cmd.command == CommandType.HELP:
        return await _handle_help()
    return await _safe_llm_response(inbound, settings)


async def handle_twilio_message(form_data: dict[str, str], settings: Settings) -> None:
    logger.info("Twilio webhook received")
    inbound = parse_twilio_inbound(form_data)
    if not inbound:
        logger.warning("Could not parse Twilio inbound (missing From?)")
        return

    phone_hash = pseudonymize_user_id(inbound.sender_id, settings.salt)
    user_key = phone_hash[:16]
    logger.info("Parsed inbound from user=%s...", user_key[:8])

    twilio_client = TwilioService(
        account_sid=settings.twilio_account_sid,
        auth_token=settings.twilio_auth_token,
        whatsapp_number=settings.twilio_whatsapp_number,
        mock_mode=settings.mock_mode,
    )

    # Commands are instant — no debounce or thinking UX needed.
    cmd = parse_command(inbound.text or "")
    if cmd is not None:
        response_text = await _process_and_reply(inbound, settings)
        try:
            await twilio_client.send_text(to=inbound.sender_id, message=response_text)
            logger.info("Twilio command response sent to user=%s...", user_key[:8])
        except Exception as exc:
            logger.exception("Twilio send failed for command (user=%s...): %s", user_key[:8], exc)
        return

    # Regular message: debounce 3s, then thinking UX.
    my_token = time.monotonic()
    _last_seen[user_key] = my_token

    await asyncio.sleep(3.0)

    if _last_seen.get(user_key) != my_token:
        logger.info("Debounced message from user=%s...", user_key[:8])
        return

    # Past the debounce gate — Playlab call starts here.
    try:
        await twilio_client.send_text(to=inbound.sender_id, message="Thinking...")
    except Exception:
        logger.warning("Failed to send Thinking... to user=%s...", user_key[:8], exc_info=True)

    still_working_task = asyncio.create_task(
        _send_delayed(twilio_client, inbound.sender_id, "Still working on it...", delay=5.0)
    )

    try:
        response_text = await process_inbound_message(inbound, settings)
        await twilio_client.send_text(to=inbound.sender_id, message=response_text)
        logger.info("Twilio response sent to user=%s...", user_key[:8])
    except Exception as exc:
        logger.exception("LLM call failed for user=%s...: %s", user_key[:8], exc)
        try:
            await twilio_client.send_text(
                to=inbound.sender_id, message="Something went wrong, please try again?"
            )
        except Exception:
            logger.warning("Failed to send error message to user=%s...", user_key[:8])
    finally:
        still_working_task.cancel()
        try:
            await still_working_task
        except asyncio.CancelledError:
            pass


async def _send_delayed(twilio_client: TwilioService, to: str, message: str, delay: float) -> None:
    await asyncio.sleep(delay)
    try:
        await twilio_client.send_text(to=to, message=message)
    except Exception:
        logger.warning("Failed to send delayed message to %s", to, exc_info=True)


async def handle_meta_message(json_data: dict, settings: Settings) -> None:
    """Handle an inbound WhatsApp message from Meta Cloud API."""
    from app.parsers.meta import parse_inbound as parse_meta_inbound
    from app.services.meta_service import MetaService

    logger.info("Meta webhook received")
    inbound = parse_meta_inbound(json_data)
    if not inbound:
        logger.info("Meta webhook had no inbound message (likely a status update)")
        return

    phone_hash = pseudonymize_user_id(inbound.sender_id, settings.salt)
    user_key = phone_hash[:16]
    logger.info("Parsed inbound from user=%s...", user_key[:8])

    meta_client = MetaService(
        access_token=settings.meta_access_token,
        phone_number_id=settings.meta_phone_number_id,
        mock_mode=settings.mock_mode,
    )

    # Commands are instant — no debounce or typing UX needed.
    cmd = parse_command(inbound.text or "")
    if cmd is not None:
        response_text = await _process_and_reply(inbound, settings)
        try:
            await meta_client.send_text(to=inbound.sender_id, message=response_text)
            logger.info("Meta command response sent to user=%s...", user_key[:8])
        except Exception as exc:
            logger.exception("Meta send failed for command (user=%s...): %s", user_key[:8], exc)
        return

    # Regular message: debounce 3s, then typing + read receipt UX.
    my_token = time.monotonic()
    _last_seen[user_key] = my_token

    await asyncio.sleep(3.0)

    if _last_seen.get(user_key) != my_token:
        logger.info("Debounced Meta message from user=%s...", user_key[:8])
        return

    # Past the debounce gate — Playlab call starts here.
    # adjustment #2: only mark_read when message_id is present.
    if inbound.message_id:
        try:
            await meta_client.mark_read(inbound.message_id)
        except Exception:
            logger.warning("mark_read failed for user=%s...", user_key[:8], exc_info=True)

    try:
        await meta_client.send_typing_on(inbound.sender_id)
    except Exception:
        logger.warning("send_typing_on failed for user=%s...", user_key[:8], exc_info=True)

    # adjustment #1: refresh and interim tasks are cancelled in finally so the
    # typing loop never outlives the handler on either success or error paths.
    refresh_task = asyncio.create_task(
        _refresh_typing(meta_client, inbound.sender_id)
    )
    interim_task = asyncio.create_task(
        _send_delayed_meta(meta_client, inbound.sender_id, "One moment, checking that...", delay=2.0)
    )

    try:
        response_text = await process_inbound_message(inbound, settings)
        await meta_client.send_text(to=inbound.sender_id, message=response_text)
        logger.info("Meta response sent to user=%s...", user_key[:8])
    except Exception as exc:
        logger.exception("LLM call failed for user=%s...: %s", user_key[:8], exc)
        try:
            await meta_client.send_text(
                to=inbound.sender_id, message="Something went wrong, please try again?"
            )
        except Exception:
            logger.warning("Failed to send error message to user=%s...", user_key[:8])
    finally:
        # Cancel both background tasks on every exit path (adjustment #1).
        refresh_task.cancel()
        interim_task.cancel()
        for task in (refresh_task, interim_task):
            try:
                await task
            except asyncio.CancelledError:
                pass
        try:
            await meta_client.send_typing_off(inbound.sender_id)
        except Exception:
            logger.warning("send_typing_off failed for user=%s...", user_key[:8], exc_info=True)


async def _refresh_typing(meta_client, to: str) -> None:
    """Re-send typing_on every 20s so Meta's 25s expiry doesn't drop the indicator."""
    while True:
        await asyncio.sleep(20.0)
        try:
            await meta_client.send_typing_on(to)
        except Exception:
            logger.warning("_refresh_typing: send_typing_on failed for %s", to, exc_info=True)


async def _send_delayed_meta(meta_client, to: str, message: str, delay: float) -> None:
    await asyncio.sleep(delay)
    try:
        await meta_client.send_text(to=to, message=message)
    except Exception:
        logger.warning("Failed to send delayed Meta message to %s", to, exc_info=True)
