import base64
import hashlib
import hmac
import logging
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.core.config import get_settings
from app.workflows.bridge import handle_meta_message, handle_twilio_message

logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
) -> Response:
    """Meta webhook verification handshake.

    Meta sends a GET with hub.mode, hub.verify_token, and hub.challenge.
    We check the token matches our config and echo back the challenge.
    """
    if not hub_mode or not hub_challenge or not hub_verify_token:
        raise HTTPException(status_code=400, detail="Missing webhook parameters")

    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        logger.info("Meta webhook verified successfully")
        return Response(content=hub_challenge, media_type="text/plain")

    logger.warning("Meta webhook verification failed: token mismatch")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def receive_webhook(request: Request) -> dict[str, str]:
    """Handle inbound webhook from either Twilio or Meta.

    Routes to the correct handler based on WHATSAPP_PROVIDER setting.
    """
    try:
        settings = get_settings()
        content_type = request.headers.get("content-type", "")
        logger.info("Webhook POST received, content-type: %s", content_type)

        if settings.whatsapp_provider == "meta":
            # Meta sends JSON with X-Hub-Signature-256 for verification.
            raw_body = await request.body()
            _verify_meta_signature(request, raw_body, settings.meta_app_secret)

            json_data = await request.json()
            await handle_meta_message(json_data, settings)
        else:
            # Twilio sends form-encoded data.
            try:
                form = await request.form()
                form_data = dict(form)
            except Exception:
                raw_body = (await request.body()).decode("utf-8", errors="replace")
                form_data = {
                    key: values[0] if values else "" for key, values in parse_qs(raw_body).items()
                }
            _verify_twilio_signature(request, form_data, settings.twilio_auth_token)
            await handle_twilio_message(form_data, settings)

        return {"status": "accepted"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Webhook handler failed: %s", exc)
        raise


def _verify_meta_signature(request: Request, body: bytes, app_secret: str) -> None:
    """Verify the X-Hub-Signature-256 header from Meta.

    Meta signs every webhook POST with HMAC-SHA256 using the App Secret.
    We verify this to ensure the request is genuinely from Meta.
    """
    if not app_secret:
        logger.error("META_APP_SECRET not configured — cannot verify webhook")
        raise HTTPException(status_code=500, detail="Server misconfiguration")

    signature_header = request.headers.get("x-hub-signature-256", "")
    if not signature_header:
        logger.warning("Missing X-Hub-Signature-256 header")
        raise HTTPException(status_code=403, detail="Missing signature")

    expected = (
        "sha256="
        + hmac.new(
            app_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
    )

    if not hmac.compare_digest(expected, signature_header):
        logger.warning("Meta webhook signature mismatch")
        raise HTTPException(status_code=403, detail="Invalid signature")


def _verify_twilio_signature(request: Request, form_data: dict[str, str], auth_token: str) -> None:
    """Verify the X-Twilio-Signature header.

    Twilio signs every webhook POST with HMAC-SHA1 using the Auth Token.
    The signature is computed over the request URL + sorted POST parameters.
    No external SDK required — we replicate Twilio's algorithm directly.
    """
    if not auth_token or auth_token == "unused":
        logger.error("TWILIO_AUTH_TOKEN not configured — cannot verify webhook")
        raise HTTPException(status_code=500, detail="Server misconfiguration")

    signature = request.headers.get("x-twilio-signature", "")
    if not signature:
        logger.warning("Missing X-Twilio-Signature header")
        raise HTTPException(status_code=403, detail="Missing signature")

    # Twilio's algorithm: URL + sorted key-value pairs, then HMAC-SHA1 + base64.
    url = str(request.url)
    data_str = url + "".join(f"{k}{v}" for k, v in sorted(form_data.items()))
    expected = base64.b64encode(
        hmac.new(auth_token.encode(), data_str.encode("utf-8"), hashlib.sha1).digest()
    ).decode()

    if not hmac.compare_digest(expected, signature):
        logger.warning("Twilio webhook signature mismatch")
        raise HTTPException(status_code=403, detail="Invalid signature")
