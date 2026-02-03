from fastapi import FastAPI

from app.api.router import router as api_router


app = FastAPI()
# Central router keeps HTTP surface area organized.
app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
    # Simple readiness response for local dev and basic uptime checks.
    return {"status": "ok"}
