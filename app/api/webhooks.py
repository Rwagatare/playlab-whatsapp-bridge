from fastapi import APIRouter, HTTPException, Query


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
