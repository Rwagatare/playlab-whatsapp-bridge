from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.webhooks import router as webhooks_router

router = APIRouter()
# Keep route registration centralized for clarity.
router.include_router(health_router)
router.include_router(webhooks_router)
