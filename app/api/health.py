from fastapi import APIRouter


router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    # Minimal health probe for container orchestration and uptime checks.
    return {"status": "ok"}
