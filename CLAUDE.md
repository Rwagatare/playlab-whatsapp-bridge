# playlab-whatsapp-bridge — Project Briefing

## What This Is
WhatsApp AI bridge for students. Flow: WhatsApp → Twilio → FastAPI webhook → Playlab AI (SSE) → response back via Twilio.

## Current State (as of Sprint 2 start)
- Server startup is broken due to heavy module-level imports added during DB implementation
- Playlab API SSE parsing fix is written but untested (app/services/playlab_service.py)
- DATABASE_URL=mock bypasses PostgreSQL entirely
- LLM_PROVIDER switches between playlab and claude

## The Rule That Matters Most
NEVER put these at the top of main.py or bridge.py:
  from app.db.engine import anything
  from sqlalchemy import anything
  import httpx
Move them inside the function that needs them.

## Agent Coordination Map
orchestrator → assigns tasks, never implements
startup-doctor → server up? call this first
playlab-specialist → SSE working? call this second
feature-builder → new features only, after server is stable
safety-check → always last, before every commit

## Sprint Status
Sprint 1 DONE: Twilio + WhatsApp + Playlab + Claude fallback + privacy pseudonymization
Sprint 2 IN PROGRESS: Multi-user support (#26 DB models done, #27-29 blocked by startup regression)

## Immediate Goal
1. startup-doctor fixes server startup
2. playlab-specialist confirms end-to-end flow works
3. safety-check approves
4. commit + push clean state
5. resume Sprint 2 features
