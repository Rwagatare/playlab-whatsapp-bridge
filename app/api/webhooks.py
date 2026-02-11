import logging
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.config import get_settings
from app.workflows.bridge import handle_inbound_message, handle_twilio_message

logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
) -> str:
    # Meta verification handshake: echo back the hub.challenge.
    if not hub_mode or not hub_challenge or not hub_verify_token:
        raise HTTPException(status_code=400, detail="Missing webhook parameters")
    # Placeholder until verify token is introduced in later sprint.
    return hub_challenge


@router.post("/webhook")
async def receive_webhook(request: Request) -> dict[str, str]:
    # Minimal inbound handler; orchestration lives in the workflow layer.
    try:
        settings = get_settings()
        content_type = request.headers.get("content-type", "")
        logger.info("Webhook POST received, content-type: %s", content_type)

        if content_type.startswith("application/json"):
            payload = await request.json()
            await handle_inbound_message(payload, settings)
        else:
            try:
                form = await request.form()
                form_data = dict(form)
            except Exception:
                raw_body = (await request.body()).decode("utf-8", errors="replace")
                form_data = {
                    key: values[0] if values else ""
                    for key, values in parse_qs(raw_body).items()
                }
            await handle_twilio_message(form_data, settings)
        return {"status": "accepted"}
    except Exception as exc:
        logger.exception("Webhook handler failed: %s", exc)
        raise
