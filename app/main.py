from fastapi import FastAPI
from pydantic import BaseModel

from app.api.router import router as api_router
from app.core.config import get_settings
from app.services.playlab_service import PlaylabService


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
    )
    conversation_id = await service.create_conversation()
    response_text = await service.send_message(conversation_id, payload.message)
    return {"response": response_text}
