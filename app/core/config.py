import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    salt: str
    mock_mode: bool
    provider: str
    playlab_api_key: str
    playlab_project_id: str
    playlab_base_url: str
    turnio_api_key: str
    turnio_base_url: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_number: str
    llm_provider: str
    anthropic_api_key: str
    claude_model: str
    claude_system_prompt: str


def _get_env(name: str) -> str:
    # Fail fast so missing secrets surface early in dev and CI.
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _get_env_optional(name: str, default: str = "") -> str:
    value = os.getenv(name, "").strip()
    return value or default


def _get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_settings() -> Settings:
    # Centralized configuration access point.
    mock_mode = _get_bool_env("MOCK_MODE", default=False)
    provider = _get_env_optional("PROVIDER", "turnio").lower()
    llm_provider = _get_env_optional("LLM_PROVIDER", "playlab").lower()
    claude_model = _get_env_optional("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
    claude_system_prompt = _get_env_optional(
        "CLAUDE_SYSTEM_PROMPT",
        "You are a helpful assistant on WhatsApp. Keep responses concise and friendly.",
    )
    if mock_mode:
        return Settings(
            database_url=_get_env_optional("DATABASE_URL", "mock"),
            redis_url=_get_env_optional("REDIS_URL", "mock"),
            salt=_get_env_optional("SALT", "mock-salt"),
            mock_mode=True,
            provider=provider,
            playlab_api_key=_get_env_optional("PLAYLAB_API_KEY", "mock"),
            playlab_project_id=_get_env_optional("PLAYLAB_PROJECT_ID", "mock"),
            playlab_base_url=_get_env_optional("PLAYLAB_BASE_URL", "mock"),
            turnio_api_key=_get_env_optional("TURNIO_API_KEY", "mock"),
            turnio_base_url=_get_env_optional("TURNIO_BASE_URL", "mock"),
            twilio_account_sid=_get_env_optional("TWILIO_ACCOUNT_SID", "mock"),
            twilio_auth_token=_get_env_optional("TWILIO_AUTH_TOKEN", "mock"),
            twilio_whatsapp_number=_get_env_optional(
                "TWILIO_WHATSAPP_NUMBER",
                "mock",
            ),
            llm_provider=llm_provider,
            anthropic_api_key=_get_env_optional("ANTHROPIC_API_KEY", "mock"),
            claude_model=claude_model,
            claude_system_prompt=claude_system_prompt,
        )
    return Settings(
        database_url=_get_env_optional("DATABASE_URL", ""),
        redis_url=_get_env_optional("REDIS_URL", ""),
        salt=_get_env("SALT"),
        mock_mode=False,
        provider=provider,
        playlab_api_key=_get_env_optional("PLAYLAB_API_KEY", "unused"),
        playlab_project_id=_get_env_optional("PLAYLAB_PROJECT_ID", "unused"),
        playlab_base_url=_get_env_optional("PLAYLAB_BASE_URL", "unused"),
        turnio_api_key=_get_env_optional("TURNIO_API_KEY", "unused"),
        turnio_base_url=_get_env_optional("TURNIO_BASE_URL", "unused"),
        twilio_account_sid=_get_env_optional("TWILIO_ACCOUNT_SID", "unused"),
        twilio_auth_token=_get_env_optional("TWILIO_AUTH_TOKEN", "unused"),
        twilio_whatsapp_number=_get_env_optional(
            "TWILIO_WHATSAPP_NUMBER",
            "unused",
        ),
        llm_provider=llm_provider,
        anthropic_api_key=_get_env_optional("ANTHROPIC_API_KEY", ""),
        claude_model=claude_model,
        claude_system_prompt=claude_system_prompt,
    )
