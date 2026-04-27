# playlab-whatsapp-bridge

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue) ![License MIT](https://img.shields.io/badge/license-MIT-green) ![Deploy](https://img.shields.io/badge/deploy-fly.io-purple)

A WhatsApp bridge that connects students in low-connectivity regions to AI tutoring bots powered by Playlab, so they can learn through a messaging app they already have.

## Motivation

Built for students in low-connectivity regions of the Global South, where smartphones are common but data is expensive and unreliable. WhatsApp was chosen because it is the dominant messaging platform in these regions and works well on limited data plans. The bridge connects to Playlab AI tutoring bots so students can access high-quality learning experiences through a familiar interface without needing a separate app or stable internet connection.

Developed as a senior capstone project at Westmont College in collaboration with MIT Media Lab.

## Architecture

The server is built on FastAPI with a provider abstraction layer that makes the WhatsApp provider (Meta Cloud API or Twilio) and LLM provider (Playlab or Claude) swappable via environment variables — no code changes needed to switch. All message processing is async throughout, so the webhook returns 200 immediately and processing happens in the background. Conversations are isolated per bot using a `bot_key` field in the session model, so switching bots starts a fresh conversation without losing history from the previous one. The multi-bot registry is loaded at startup from the `PLAYLAB_BOTS` environment variable, making it easy to add or remove bots without touching code.

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
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
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
   uv sync
   uv add aiosqlite
   ```

2. **Configure environment:**
   Create a `.env` file (see Environment Variables below) with your API keys and settings.

3. **Start the server:**

   ```bash
   uv run uvicorn app.main:app --reload --port 8000
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
   - In the Twilio Console, go to Messaging > Sandbox settings
   - Set the webhook URL to: `https://<your-ngrok-id>.ngrok-free.dev/webhook` (POST)

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
PLAYLAB_PROJECT_ID=your-default-project-id
PLAYLAB_BASE_URL=https://www.playlab.ai/api/v1

# Multi-bot registry — first entry is the default bot.
# Format: Display Name:slug:project_id (comma-separated)
PLAYLAB_BOTS=Welcome Guide:guide:project_id_1,AI or Not:ai-or-not:project_id_2,Teachable Machine:teachable-machine:project_id_3

# Anthropic Claude (required if LLM_PROVIDER=claude)
ANTHROPIC_API_KEY=your-api-key
CLAUDE_MODEL=claude-sonnet-4-6
CLAUDE_SYSTEM_PROMPT=You are a helpful assistant on WhatsApp. Keep responses concise and friendly.

# App
MOCK_MODE=0
SALT=your-random-salt
DATABASE_URL=sqlite+aiosqlite:///./playlab_bridge.db
```

## User Commands

Users can type these commands directly in WhatsApp:

| Command          | Description                                          |
| ---------------- | ---------------------------------------------------- |
| `/bots`          | List all available bots                              |
| `/switch <slug>` | Switch to a different bot (e.g. `/switch ai-or-not`) |
| `/current`       | Show which bot is currently active                   |
| `/reset`         | Clear conversation history and start fresh           |
| `/help`          | Show all available commands                          |

## UX Behaviour

**Twilio (dev/demo):**

- Messages are debounced for 3 seconds — if a user sends multiple messages quickly, only the last one is processed
- A `Thinking...` message is sent immediately while waiting for Playlab
- If the response takes longer than 5 seconds, a `Still working on it...` message is sent

**Meta Cloud API (production):**

- 3 second debounce, same as Twilio
- Blue double-tick read receipt is sent instantly on message receipt
- A `...` typing indicator is shown while Playlab processes the message
- The typing indicator is refreshed every 20 seconds so it never expires
- An interim `One moment, checking that...` message is sent if the response takes longer than 2 seconds

## Multi-Bot Setup

Add bots to `PLAYLAB_BOTS` as comma-separated entries in the format `Display Name:slug:project_id`. The **first entry is the default** bot new users are assigned to. Each bot's project ID comes from its Playlab project URL.

Multi-bot support lets students interact with different AI tutors within the same WhatsApp number — for example, a Welcome Guide that onboards new users, and an AI-or-Not activity bot for a specific lesson. Conversation history is isolated per bot, so switching bots starts a fresh session without losing the previous one.

```bash
PLAYLAB_BOTS=Welcome Guide:guide:abc123,AI or Not:ai-or-not:def456
```

Users switch bots with `/switch <slug>`, e.g. `/switch ai-or-not`.

## Test Endpoints

These endpoints are only available when `MOCK_MODE=1` (disabled in production):

| Endpoint        | Method | Description                                                               |
| --------------- | ------ | ------------------------------------------------------------------------- |
| `/health`       | GET    | Health check (always available)                                           |
| `/test-claude`  | POST   | Test Claude: `{"message": "Hello"}`                                       |
| `/test-playlab` | POST   | Test Playlab: `{"message": "Hello"}`                                      |
| `/demo/bridge`  | POST   | Full bridge without WhatsApp: `{"message": "Hello", "sender_id": "test"}` |

## Running Tests

```bash
uv run pytest tests/ -v
```

## Deployment

The production server runs on [Fly.io](https://fly.io). Key differences from local dev:

- `DATABASE_URL` — set to a PostgreSQL connection string (not SQLite); run Alembic migrations before deploying
- `WHATSAPP_PROVIDER=meta` — production uses Meta Cloud API, not Twilio
- `MOCK_MODE=0` — must be off in production
- The production WhatsApp number is **+27 87 373 1522**

## Docker

```bash
# Set POSTGRES_PASSWORD in your .env first
docker-compose up --build
```

## Secret Safety

- **Never** commit `.env` or any real keys
- `.env` is already in `.gitignore`
- Use a cryptographically random salt: `python -c "import secrets; print(secrets.token_hex(32))"`
- Install pre-commit hooks to scan for secrets:
  ```bash
  pip install pre-commit
  pre-commit install
  ```

## Contributing & Design Principles

1. Fork the repo
2. Create a feature branch
3. Run tests before submitting a PR
4. Keep `.env` out of commits

Architectural conventions:

- **Frozen dataclasses** for service configuration (immutable, explicit)
- **Async throughout** — no sync I/O in the request path
- **Provider pattern** — new WhatsApp or LLM providers implement the same interface as existing ones
- **All features require tests** before merge

## License

MIT License — see [LICENSE](LICENSE) for details.
