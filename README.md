# Jarvis Core — Multi-Tenant Agentic Platform

Jarvis is a multi-tenant AI assistant platform. A single **Core Gateway** owns all
conversational logic, tenant state, and tool access; every surface the customer
talks to — Telegram today, a Next.js web app and a real-time voice agent next —
is just another **client** of that same gateway. This folder holds the Phase 0
seed: the architectural decisions that must be right on day one, so tenants 2–10
become config rows instead of rewrites, and new channels become adapters instead
of forks.

## The One Rule
**`tenant_id` flows through everything** — every table, every Chroma collection,
every LangGraph thread ID, every usage log row, every channel adapter (Telegram,
web, voice). This is the difference between a platform and a pile of scripts.

## System Overview

```
                     ┌───────────────────────────────────────────┐
                     │              JARVIS CORE GATEWAY           │
                     │            (FastAPI — main.py)             │
                     │                                             │
Telegram  ─────────▶│  Toleration → Router → Tenant LangGraph      │
(webhook, live)      │        │            │            │         │
                     │        │            ▼            │         │
Web/Voice  ─────────▶│        │      MCP tools per       │        │
(Lovable/Next.js,    │        │      tenant_tools table   │       │
 planned)            │        │            │              │      │
                     │        ▼            ▼              ▼      │
                     │   Postgres    Chroma (RAG)    usage_events │
                     │  (Supabase)   per-tenant KB     (cost/lat) │
                     └───────────────────────────────────────────┘
```

Every client — Telegram bot or web/voice frontend — is a thin adapter that
speaks the gateway's internal event schema. None of them own conversation
state or business logic; the gateway does, backed by Postgres.

### Planned real-time voice path (Lovable/Next.js frontend)

The web frontend (scaffolded with Lovable + Next.js) is being extended with a
voice agent. Because voice needs full-duplex, low-latency exchange rather than
one-shot request/response, it will **not** use the REST pattern that Telegram's
webhook uses. Instead:

```
Browser mic (Web Audio API)
   │  binary audio chunks
   ▼
WebSocket / WebRTC  ──────────────▶  Jarvis Core Gateway (orchestrator)
                                          │
                                          ├─▶ STT (e.g. Deepgram) → text
                                          ├─▶ same LLM router + tenant LangGraph
                                          │   used by the Telegram path
                                          └─▶ TTS (e.g. ElevenLabs) → audio
                                          │
   ◀───────────────────────────────────────  streamed status + audio events
Browser speaker / UI "speaking" indicator
```

Key behaviors this path needs to match Telegram's fluidity:
- **Status events**, not just final replies — `{"type": "status", "content": "thinking"}`
  drives a "typing/speaking" indicator, the voice equivalent of Telegram's
  "bot is typing…".
- **Barge-in**: if the user starts speaking while TTS audio is playing, the
  gateway sends `{"type": "stop_audio"}` and clears the playback buffer
  immediately — otherwise it feels like a broadcast, not a conversation.
- **Shared state**: the web/voice session and a user's Telegram session for
  the same tenant read and write the same `users` / `messages` rows, so the
  agent doesn't "forget" context when a customer switches channels.
- **Server-side secrets only**: STT/TTS/LLM API keys stay on the gateway; the
  browser only ever holds a short-lived session token.

This is additive to the existing architecture, not a replacement — Telegram
keeps using the webhook/REST path in `main.py`; voice gets a new WebSocket
route on the same gateway, and both funnel into the same toleration → router →
LangGraph → usage_events pipeline.

## The Switchbox — how it actually works
MCP gives every tool the same plug shape. The tier toggle is **not** MCP itself —
it is the `tenant_tools` table. At session start, the client reads the enabled
rows for that tenant and mounts only those MCP servers. The Founder Dashboard is
CRUD on that table:

- Tenant upgrades to premium → flip `channel.whatsapp` to enabled, `channel.telegram` off.
- Enable `crm.gohighlevel` for a pro tenant → one row update.
- Enable the voice channel for a tenant → flip `channel.voice_web` on, same pattern.
- Agent code never changes. That is the whole trick.

## Model Routing (llm_router.py)
| task_type | model | why |
|---|---|---|
| intent | llama3.2:3b (local) | runs thousands of times, must be ~free |
| agent_turn | qwen2.5:7b (local) → Claude Haiku (fallback) | qwen proven at multi-tool calls in your own lab |
| draft | mistral:7b (local) → Claude Sonnet (fallback) | prose quality |
| escalation | Claude Sonnet (cloud, premium tier only) | hard reasoning |

Research strategy is a router flag, not a separate system: fresh/current info →
web_search tool; tenant knowledge → RAG on the tenant's Chroma collection. The
voice path reuses this exact router for the "brain" step — only the I/O layer
(STT in, TTS out) is new.

## Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Core gateway | FastAPI (Python) | single entry point for all channels |
| Database | Postgres via Supabase | tenants, users, messages, usage_events |
| Vector store | ChromaDB (per-tenant collection) | RAG grounding, local + free |
| Chat channel (live) | Telegram Bot API, webhook | Phase 0 slice, working end-to-end |
| Web frontend (in progress) | Next.js, scaffolded via Lovable | chat UI + voice agent |
| Realtime transport (planned) | WebSockets / WebRTC | full-duplex voice, replaces REST for this path |
| STT (planned) | Deepgram (or equivalent) | low-latency speech-to-text |
| TTS (planned) | ElevenLabs (or equivalent) | low-latency, natural voice |
| Shared session state (planned) | Redis (or existing Postgres tables) | cross-channel conversation continuity |
| LLM providers | Ollama (local: llama3.2, qwen2.5, mistral) + Anthropic API (Haiku/Sonnet fallback) | matrix in `llm_router.py` |

## Key Features
- **Cross-platform persistence** — a customer's conversation state (and
  `moderation_state` strikes) is tenant + user scoped in Postgres, so Telegram
  and the web/voice frontend are two windows onto the same conversation, not
  two separate bots.
- **Real-time voice streaming (planned)** — WebSocket/WebRTC transport, STT →
  LLM router → TTS, with status events driving UI indicators.
- **Interruptible audio / barge-in (planned)** — user speech mid-playback
  immediately halts and clears the TTS buffer.
- **Strike-based toleration middleware** — keeps a public-facing bot from
  burning compute on off-topic chatter, with reputation-based slack.
- **Tenant switchbox** — per-tenant tool/channel enablement is a database row,
  never a code change.
- **HITL gates** — payments and large orders always pause for human approval.

## Production corrections to the lab patterns
- `MemorySaver` is in-memory only. Production uses **LangGraph's Postgres
  checkpointer** so paused HITL approvals survive restarts.
- Secrets never live in the DB — `api_key_refs` stores pointers to env vars /
  secret manager, not raw keys. The same rule applies to future STT/TTS keys:
  gateway-side only, never shipped to the browser.
- Every money-touching action (payments, large orders, B2C renewals) goes through
  a mandatory HITL `interrupt()` gate — the exact pattern from the HITL lab.

## Phase Plan
- **Phase 0 (done/near-done):** One tenant (Kesari Pipes), Telegram, local
  Chroma RAG, Postgres schema, toleration middleware, usage logging. End-to-end
  slice, working live.
- **Phase 0.5 (current):** Next.js web frontend (via Lovable) + voice agent.
  WebSocket/WebRTC bridge into the same gateway, STT/TTS integration,
  barge-in logic, shared conversation state with Telegram.
- **Phase 1:** Founder Dashboard (Streamlit) — reads `usage_events`, toggles
  `tenant_tools`. Role-based views (owner vs operator) per the earlier design.
- **Phase 2:** Second tenant onboarded purely via config to prove isolation.
  Demo the switch flip: Telegram → WhatsApp adapter for a premium tenant.
- **Phase 3:** B2C Life OS module — deferred deliberately. The CA agent touches
  bank data and money; it ships only with hard HITL gates and after B2B revenue.

## Files
- `schema.sql` — the multi-tenant foundation (run against Postgres/Supabase)
- `main.py` — FastAPI gateway; Telegram webhook live, voice WebSocket route planned
- `toleration.py` — strike system with reputation-based limits
- `llm_router.py` — model matrix + provider fallback chain
- `ingest.py` — per-tenant catalog → ChromaDB ingest with dedup
- `tenant.kesari.example.yaml` — tenant = config, never code

## What's needed next (build queue)
1. WebSocket route on the gateway for the voice/web client (audio in, status +
   audio events out).
2. STT integration (chunked audio → text) feeding the existing LLM router.
3. TTS integration (LLM text → streamed audio) with barge-in / `stop_audio`.
4. Shared event schema doc so Telegram and web/voice both map onto the same
   internal function calls (e.g. "book a meeting" behaves identically either way).
5. Verify session token issuance so the browser never sees provider API keys.
6. `standard_business_v1` LangGraph (analyse → act → HITL gate → respond).
7. MCP server skeleton for the first tool + client-side mounting from `tenant_tools`.
8. Postgres checkpointer wiring for LangGraph.
