from dataclasses import dataclass
from enum import Enum


class CommandType(Enum):
    BOTS = "bots"
    SWITCH = "switch"
    CURRENT = "current"
    HELP = "help"
    RESET = "reset"


@dataclass(frozen=True)
class CommandResult:
    command: CommandType
    args: str | None = None


def parse_command(message: str) -> CommandResult | None:
    """Return CommandResult for /commands, None for plain text or unknown /commands."""
    stripped = (message or "").strip()
    if not stripped.startswith("/"):
        return None
    parts = stripped[1:].split(None, 1)
    if not parts:
        return None
    verb = parts[0].lower()
    arg = parts[1].lower().strip() if len(parts) > 1 else None
    mapping = {
        "bots": CommandType.BOTS,
        "switch": CommandType.SWITCH,
        "current": CommandType.CURRENT,
        "help": CommandType.HELP,
        "reset": CommandType.RESET,
    }
    if verb not in mapping:
        return None
    return CommandResult(command=mapping[verb], args=arg)
