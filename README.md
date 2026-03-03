# playlab-whatsapp-bridge

A WhatsApp bridge that connects students in low-connectivity regions to AI tutoring bots powered by Playlab, so they can learn through a messaging app they already have.

## How It Works

```
WhatsApp --> Meta Cloud API / Twilio --> FastAPI (/webhook) --> Playlab --> Meta / Twilio --> WhatsApp
```

The server receives incoming WhatsApp messages via webhook, forwards them to a configurable LLM provider (Playlab or Claude), and sends the AI response back to the user. Two WhatsApp providers are supported:

- **Meta Cloud API** — production provider (direct WhatsApp Business Platform integration)
- **Twilio** — development/demo provider (free sandbox for testing)

## Quick Start

### Prerequisites
- Python 3.10+
- An API key for your chosen LLM provider ([Playlab](https://playlab.ai) or [Anthropic](https://anthropic.com))
- [ngrok](https://ngrok.com) (for local development)
- One of:
  - A [Meta Business account](https://business.facebook.com) with WhatsApp Cloud API access
  - A [Twilio](https://www.twilio.com) account (free sandbox available)

### Setup

1. **Clone and install:**
   ```bash
   git clone https://github.com/Rwagatare/playlab-whatsapp-bridge.git
   cd playlab-whatsapp-bridge
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[test]"
   ```

2. **Configure environment:**
   Create a `.env` file (see Environment Variables below) with your API keys and settings.

3. **Start the server:**
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

4. **Expose locally with ngrok** (for development):
   ```bash
   ngrok http 8000
   ```

5. **Configure your webhook:**

   **For Meta Cloud API** (`WHATSAPP_PROVIDER=meta`):
   - In the [Meta App Dashboard](https://developers.facebook.com/apps), go to WhatsApp > Configuration
   - Set the webhook URL to: `https://<your-ngrok-id>.ngrok-free.dev/webhook`
   - Set the verify token to match your `META_VERIFY_TOKEN`
   - Subscribe to the `messages` field

   **For Twilio** (`WHATSAPP_PROVIDER=twilio`):
   - In the Twilio Console, set your WhatsApp sandbox webhook URL to:
     `https://<your-ngrok-id>.ngrok-free.dev/webhook` (POST)

6. **Test:** Send a WhatsApp message to your configured number.

## Environment Variables

```bash
# WhatsApp provider: "meta" (production) or "twilio" (dev/demo)
WHATSAPP_PROVIDER=twilio

# Meta Cloud API (required if WHATSAPP_PROVIDER=meta)
META_PHONE_NUMBER_ID=your-phone-number-id
META_ACCESS_TOKEN=your-access-token
META_APP_SECRET=your-app-secret
META_VERIFY_TOKEN=your-verify-token

# Twilio (required if WHATSAPP_PROVIDER=twilio)
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# LLM Provider: "playlab" (default) or "claude"
LLM_PROVIDER=playlab

# Playlab (required if LLM_PROVIDER=playlab)
PLAYLAB_API_KEY=your-api-key
PLAYLAB_PROJECT_ID=your-project-id
PLAYLAB_BASE_URL=https://www.playlab.ai/api/v1

# Anthropic Claude (required if LLM_PROVIDER=claude)
ANTHROPIC_API_KEY=your-api-key
CLAUDE_MODEL=claude-sonnet-4-5-20250929
CLAUDE_SYSTEM_PROMPT=You are a helpful assistant on WhatsApp. Keep responses concise and friendly.

# App
MOCK_MODE=0
SALT=your-random-salt
DATABASE_URL=sqlite+aiosqlite:///./playlab_bridge.db
```

## User Commands

| Command | Description |
|---------|-------------|
| `/reset` | Clear conversation history and start fresh |

## Test Endpoints

These endpoints are only available when `MOCK_MODE=1` (disabled in production):

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check (always available) |
| `/test-claude` | POST | Test Claude: `{"message": "Hello"}` |
| `/test-playlab` | POST | Test Playlab: `{"message": "Hello"}` |
| `/demo/bridge` | POST | Full bridge without WhatsApp: `{"message": "Hello", "sender_id": "test"}` |

## Running Tests

```bash
pip install -e ".[test]"
pytest tests/ -v
```

## Docker

```bash
# Set POSTGRES_PASSWORD in your .env first
docker-compose up --build
```

## Secret Safety

- **Never** commit `.env` or any real keys
- `.env` is already in `.gitignore`
- Use a cryptographically random salt (not `dev-salt`): `python -c "import secrets; print(secrets.token_hex(32))"`
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
