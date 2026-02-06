from fastapi import APIRouter, HTTPException, Query, Request

from app.core.config import get_settings
from app.workflows.bridge import handle_inbound_message, handle_twilio_message


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
    settings = get_settings()
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        payload = await request.json()
        await handle_inbound_message(payload, settings)
    else:
        form = await request.form()
        await handle_twilio_message(dict(form), settings)
    return {"status": "accepted"}
