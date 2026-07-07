# Jarvis Core — Progress Log

## Current Status Snapshot (as of 2026-07-07)

**Completed:**
- Jarvis Core Gateway (Phase 0): FastAPI app, Supabase Postgres, `/health`
  endpoint, Telegram webhook live end-to-end (phone → Telegram → ngrok →
  gateway → reply).
- Toleration middleware, LLM router matrix, and RAG-grounded catalog answers
  (kb_keshri_pipes) all working, with usage_events logging cost/latency.
- Next.js frontend scaffolded via Lovable — initial web client for Jarvis exists.

**In Progress:**
- Designing the voice agent for the Lovable/Next.js frontend.
- Deciding on WebSocket vs WebRTC transport between the frontend and the Jarvis
  Core Gateway (moving off plain REST for this path, to support full-duplex
  audio and "barge-in" interruptions).
- Establishing the WebSocket connection itself between frontend and gateway.
- Implementing Web Audio API capture on the frontend (mic → binary chunks).

**Next Steps / Backlog:**
- Integrate STT (e.g. Deepgram) and TTS (e.g. ElevenLabs) processing in the
  gateway, sitting in front of / behind the existing LLM router.
- Implement barge-in logic: gateway emits `stop_audio` when the user speaks
  over playback; frontend clears its audio buffer immediately.
- Define the shared JSON event schema (`status`, `audio`, `stop_audio`, etc.)
  so Telegram and web/voice map onto the same internal function calls.
- Sync conversation history/state between Telegram and the Web UI (same
  tenant/user rows in Postgres, no channel-specific memory).
- Session-token issuance so the browser never holds provider API keys directly.
- Still open from Phase 0: `messages` table needs adding to `schema.sql`
  (main.py already reads/writes it), and ingest.py's doc-ID dedup should key
  off `product_id` rather than a content hash (see code_review.md).

---

## 2026-07-05
- Supabase project 'jarvis-core' created, region Mumbai (ap-south-1)
- schema.sql executed successfully — all tables live, Kesari Pipes seeded as tenant 1
- RLS disabled in dev; revisit before prod clone
- NEXT: verify tables in Table Editor, then build FastAPI gateway
- Fixed tenant name spelling in DB: keshri-pipes (yaml file on disk still needs same fix)
- SUPABASE_URL + SUPABASE_SECRET_KEY + DB password all in .env
- Gateway deps installed in jarvis-core env (fastapi, uvicorn, supabase) — cryptography fixed via conda, same as MCP lab
- Backlog: data-cleaning ingest crew (dedup), rapport agent (4 scores), lab GPU switch → AI Kosh later, Azure blob switch, ngrok wiring
- NEXT: write main.py — the FastAPI gateway, first endpoint /health, then Telegram webhook

## 2026-07-06 — Session 1 (12:00 AM – ~1:00 AM)
- main.py created: FastAPI gateway with /health endpoint
- VERIFIED: gateway connects to Supabase Mumbai, returns live tenant data
- Overwatch SRE agent backlogged: reporter first, runbook-based fixes only (no raw code exec), HITL gate on destructive actions
- Docker-per-tenant deferred until multiple paying tenants
- NEXT: Telegram webhook endpoint in main.py + ngrok tunnel so Telegram can reach the laptop

## 2026-07-06 — Session 2 (10:15 AM – ongoing)
- Telegram bot created: @Keshri_Pipes_Bot, token in .env
- ngrok installed (Intel binary via curl), authtoken registered
- VS Code set up as project kitchen (interpreter = jarvis-core, auto-activating terminals)
- Telegram webhook LIVE: phone -> Telegram servers -> ngrok -> gateway -> echo reply verified
- ngrok free tier = new URL each restart -> re-run setWebhook (see COMMANDS.md)
- Backlog: reserved/owned domain (api.keshripipes.in) at deployment
- NEXT: identify tenant + user from update -> users table comes alive

- FIRST LLM REPLY LIVE: ask_llm() via tunnel to dslab llama3.2:3b, persona working
- Known gap (by design): answers are ungrounded hallucination — RAG on kb_keshri_pipes is the fix
- NEXT: sample Keshri catalog data -> ingest into Chroma -> ground the bot's answers

- RAG GROUNDED: bot quotes KP001 @ Rs450 correctly, refuses to invent copper pipes
- Before/after hallucination proof captured (screenshot) — demo gold for Jul 26
- usage_events logging live from row 1 (tokens, latency, cost=0)
- Ingest pipeline with content-hash dedup = seed of data-cleaning crew
- NEXT: conversation memory (bot forgets everything between messages) OR broadcast machinery (festival greetings + payment follow-up share 70%)

## 2026-07-07 — Frontend + Voice Agent Kickoff
- Generated the Jarvis web frontend using Lovable + Next.js.
- Scoped the voice agent integration: moving this path to WebSockets/WebRTC
  instead of REST, so the frontend and gateway can hold a persistent,
  full-duplex connection (mirrors why Telegram feels fluid — webhook/stream,
  not poll-per-message).
- Sketched the event schema direction: `status` events (thinking/speaking) for
  UI indicators, `audio` events for TTS playback, `stop_audio` for barge-in.
- Decision: Telegram and the web/voice frontend will read/write the same
  `users`/`messages` rows so a customer's context carries across channels.
- NEXT: stand up the WebSocket route on the gateway, wire Web Audio API mic
  capture on the frontend, then bring in STT/TTS providers.
