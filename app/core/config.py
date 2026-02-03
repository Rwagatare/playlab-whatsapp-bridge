import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    salt: str
    playlab_api_key: str
    turnio_api_key: str


def _get_env(name: str) -> str:
    # Fail fast so missing secrets surface early in dev and CI.
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_settings() -> Settings:
    # Centralized configuration access point.
    return Settings(
        database_url=_get_env("DATABASE_URL"),
        redis_url=_get_env("REDIS_URL"),
        salt=_get_env("SALT"),
        playlab_api_key=_get_env("PLAYLAB_API_KEY"),
        turnio_api_key=_get_env("TURNIO_API_KEY"),
    )
