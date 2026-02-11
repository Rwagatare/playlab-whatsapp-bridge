import logging
from dataclasses import dataclass

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClaudeService:
    api_key: str
    model: str
    system_prompt: str
    mock_mode: bool = False

    async def send_message(self, message: str) -> str:
        """Send a message to Claude and return the response text."""
        if self.mock_mode:
            return f"Mock Claude response: {message}"

        client = AsyncAnthropic(api_key=self.api_key)
        logger.info("Claude send_message: model=%s", self.model)
        try:
            response = await client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self.system_prompt,
                messages=[
                    {"role": "user", "content": message},
                ],
            )
        except Exception as exc:
            logger.exception("Claude API call failed: %s", exc)
            raise RuntimeError(f"Claude message send failed: {exc}") from exc

        if not response.content:
            raise RuntimeError("Claude response contained no content blocks")

        return response.content[0].text
