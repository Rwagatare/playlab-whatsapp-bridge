# playlab-whatsapp-bridge

A WhatsApp bridge that connects AI agents with students via messaging, enabling educators to deploy custom AI assistants directly to mobile devices in low-bandwidth regions.

## How It Works

```
WhatsApp --> Twilio --> FastAPI (/webhook) --> LLM Provider --> Twilio --> WhatsApp
```

The server receives incoming WhatsApp messages via webhook, forwards them to a configurable LLM provider, and sends the AI response back to the user.

## Quick Start

### Prerequisites
- Python 3.10+
- A [Twilio](https://www.twilio.com) account (free sandbox available for WhatsApp development and testing)
- An API key for your chosen LLM provider
- [ngrok](https://ngrok.com) (for local development only)

### Setup

1. **Clone and install:**
   ```bash
   git clone https://github.com/Rwagatare/playlab-whatsapp-bridge.git
   cd playlab-whatsapp-bridge
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. **Configure environment:**
   Create a `.env` file (see Environment Variables below) with your API keys and settings.

3. **Start the server:**
   ```bash
   # Use the venv's interpreter to avoid accidentally running a global/pyenv uvicorn
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

4. **Expose locally with ngrok** (for development):
   ```bash
   ngrok http 8000
   ```

5. **Configure Twilio webhook:**
   - In the Twilio Console, set your WhatsApp sandbox webhook URL to:
     `https://<your-ngrok-id>.ngrok-free.dev/webhook` (POST)

6. **Test:** Send a WhatsApp message to your Twilio sandbox number.

## Environment Variables

```bash
# LLM Provider: the AI backend to use (e.g. "claude", "playlab")
LLM_PROVIDER=claude

# Anthropic (Claude) - required if LLM_PROVIDER=claude
ANTHROPIC_API_KEY=your-api-key
CLAUDE_MODEL=claude-sonnet-4-5-20250929
CLAUDE_SYSTEM_PROMPT=You are a helpful assistant on WhatsApp. Keep responses concise and friendly.

# Playlab - required if LLM_PROVIDER=playlab
PLAYLAB_API_KEY=your-api-key
PLAYLAB_PROJECT_ID=your-project-id
PLAYLAB_BASE_URL=https://www.playlab.ai/api/v1

# Twilio (found at twilio.com/console)
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# App
MOCK_MODE=0
SALT=your-random-salt
DATABASE_URL=postgresql+asyncpg://playlab:playlab@localhost:5432/playlab_bridge
REDIS_URL=redis://localhost:6379/0
```

## Test Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/test-claude` | POST | Test Claude: `{"message": "Hello"}` |
| `/test-playlab` | POST | Test Playlab: `{"message": "Hello"}` |
| `/demo/bridge` | POST | Full bridge without Twilio: `{"message": "Hello", "sender_id": "test"}` |

## Reset Conversations

To clear all conversations and start fresh (useful during local development):

```bash
docker compose exec db psql -U playlab playlab_bridge -c "TRUNCATE messages, conversations RESTART IDENTITY CASCADE;"
```

## Running Tests

```bash
pytest tests/ -v
```

## Docker

```bash
docker-compose up --build
```

## Secret Safety

- **Never** commit `.env` or any real keys
- `.env` is already in `.gitignore`
- Install pre-commit hooks to scan for secrets:
  ```bash
  pip install pre-commit
  pre-commit install
  ```

## Contributing

1. Fork the repo
2. Create a feature branch
3. Follow existing patterns (frozen dataclasses for services, async methods)
4. Run tests before submitting a PR
5. Keep `.env` out of commits
