import logging

from fastapi import FastAPI
from dotenv import load_dotenv
from pydantic import BaseModel

from app.api.router import router as api_router
from app.core.config import get_settings
from app.schemas.inbound import InboundMessage
from app.services.claude_service import ClaudeService
from app.services.playlab_service import PlaylabService
from app.workflows.bridge import process_inbound_message

# Configure logging so we can see what's happening
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI()
# Central router keeps HTTP surface area organized.
app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
    # Simple readiness response for local dev and basic uptime checks.
    return {"status": "ok"}


class TestPlaylabRequest(BaseModel):
    message: str


@app.post("/test-playlab")
async def test_playlab(payload: TestPlaylabRequest) -> dict[str, str]:
    # Lightweight endpoint to validate Playlab connectivity.
    settings = get_settings()
    service = PlaylabService(
        api_key=settings.playlab_api_key,
        project_id=settings.playlab_project_id,
        base_url=settings.playlab_base_url,
        mock_mode=settings.mock_mode,
    )
    conversation_id = await service.create_conversation()
    response_text = await service.send_message(conversation_id, payload.message)
    return {"response": response_text}


@app.post("/test-claude")
async def test_claude(payload: TestPlaylabRequest) -> dict[str, str]:
    # Lightweight endpoint to validate Claude connectivity.
    settings = get_settings()
    service = ClaudeService(
        api_key=settings.anthropic_api_key,
        model=settings.claude_model,
        system_prompt=settings.claude_system_prompt,
        mock_mode=settings.mock_mode,
    )
    response_text = await service.send_message(payload.message)
    return {"response": response_text}


class DemoBridgeRequest(BaseModel):
    message: str
    sender_id: str = "demo-user"


@app.post("/demo/bridge")
async def demo_bridge(payload: DemoBridgeRequest) -> dict[str, str]:
    # Demo endpoint that runs the full bridge flow without external sends.
    settings = get_settings()
    inbound = InboundMessage(
        sender_id=payload.sender_id,
        text=payload.message,
        image_url=None,
    )
    response_text = await process_inbound_message(inbound, settings)
    return {"response": response_text}
