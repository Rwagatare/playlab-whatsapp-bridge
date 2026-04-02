from dataclasses import dataclass


@dataclass(frozen=True)
class BotConfig:
    display_name: str  # "AI or Not"
    slug: str          # "ai-or-not"
    project_id: str    # "cmd3j9ksa0x03er0u7k9m0pgl"


def parse_bot_registry(env_val: str) -> list[BotConfig]:
    """Parse PLAYLAB_BOTS=DisplayName:slug:project_id,... silently skipping bad entries."""
    bots = []
    for entry in env_val.split(","):
        parts = entry.strip().split(":")
        if len(parts) != 3 or not all(parts):
            continue
        bots.append(BotConfig(display_name=parts[0], slug=parts[1], project_id=parts[2]))
    return bots


def get_bot_by_slug(registry: list[BotConfig], slug: str) -> BotConfig | None:
    for bot in registry:
        if bot.slug == slug:
            return bot
    return None


def get_default_bot(registry: list[BotConfig]) -> BotConfig | None:
    return registry[0] if registry else None
