import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.engine import dispose_engine, init_engine

    settings = get_settings()
    if settings.database_url and settings.database_url != "mock":
        init_engine(settings.database_url)
        # For SQLite, create tables directly (Alembic targets PostgreSQL).
        if settings.database_url.startswith("sqlite"):
            import app.db.models  # noqa: F401 — register models with Base
            from app.db.base import Base
            from app.db.engine import _engine

            async with _engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("SQLite tables created")
        logger.info("Database engine ready")
    else:
        logger.warning("DATABASE_URL not set or mock; running without persistence")
    yield
    await dispose_engine()


app = FastAPI(lifespan=lifespan)
# Central router keeps HTTP surface area organized.
app.include_router(api_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions so stack traces are never leaked to clients."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/")
async def root() -> dict[str, str]:
    # Simple readiness response for local dev and basic uptime checks.
    return {"status": "ok"}


def _require_mock_mode() -> None:
    """Guard that rejects requests when MOCK_MODE is off (i.e. production)."""
    settings = get_settings()
    if not settings.mock_mode:
        raise HTTPException(status_code=404, detail="Not found")


class TestPlaylabRequest(BaseModel):
    message: str = Field(..., max_length=10000)


@app.post("/test-playlab")
async def test_playlab(payload: TestPlaylabRequest) -> dict[str, str]:
    _require_mock_mode()
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
    _require_mock_mode()
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
    message: str = Field(..., max_length=10000)
    sender_id: str = "demo-user"


@app.post("/demo/bridge")
async def demo_bridge(payload: DemoBridgeRequest) -> dict[str, str]:
    _require_mock_mode()
    settings = get_settings()
    inbound = InboundMessage(
        sender_id=payload.sender_id,
        text=payload.message,
        image_url=None,
    )
    response_text = await process_inbound_message(inbound, settings)
    return {"response": response_text}
