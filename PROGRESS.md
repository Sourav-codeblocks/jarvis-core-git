# Jarvis Core — Progress Log

## Current Status Snapshot (as of 2026-07-08)

**Completed:**
- Jarvis Core Gateway (Phase 0): FastAPI app, Supabase Postgres, `/health`
  endpoint, Telegram webhook live end-to-end.
- Toleration middleware, LLM router matrix, and RAG-grounded catalog answers
  (kb_keshri_pipes) all working, with usage_events logging cost/latency.
- Next.js customer frontend scaffolded via Lovable (`frontend/`).
- **Founder's Core** (`founders-core/`) — a second, business-owner-facing
  frontend, fully wired to a real voice pipeline:
  - Mic capture → Deepgram live STT → real tool-calling (qwen2.5:7b via
    Ollama) → founder tool registry → spoken answer (Deepgram Aura-2 TTS)
    + visual overlay, round-tripping over WebSocket.
  - Two-tier LLM routing: qwen2.5 (tools attached) decides if a report
    tool fits; llama3.1:8b (no tools) handles general/personal questions
    the tools don't cover.
  - Typed-chat path shares the same brain (`route_founder_query()`) as voice.
  - Two tools wired to real data: `get_usage_report` (Postgres via
    Supabase) and `get_catalog_report` (ChromaDB, real similarity search
    when a search term is extracted). Four more (revenue/runway/
    pipeline/briefing) still fixtures.
  - Continuous "Call" mode with barge-in (stops mid-sentence the instant
    the founder starts talking again).
  - CORS configured on the gateway for the frontend's origin.
  - Full architecture reference written up in `WORKING.md`.

**In Progress / Known Gaps:**
- Founder path has no conversation memory — every query is stateless.
- `tenant_id` hardcoded to 1 throughout the founder/voice path.
- No `usage_events` logging for founder queries yet.
- Four of six founder tools are still mock fixtures.
- `founder_ws.py` calls Ollama directly rather than through `llm_router.py`.

**Next Steps / Backlog:**
- Wire remaining founder tools to real data.
- Add conversation history threading for the founder path.
- Tenant-dynamic resolution (same fix needed on the Telegram side too).
- Fix the `kb_keshri_pipes` / `kb_kesari_pipes` naming mismatch
  (flagged in `code_review.md`).
- `messages` table still needs adding to `schema.sql` (main.py already
  reads/writes it); ingest.py's dedup should key off `product_id`.

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

## 2026-07-08 — Founder's Core: full voice pipeline, start to finish
- Added Founder's Core (Lovable-generated) as a second frontend
  (`founders-core/`) — business-owner HUD with reports, captions, voice.
- Built the real WebSocket bridge: `founder_ws.py` (chat) and
  `voice_bridge.py` (voice), replacing `dataAdapter.ts`'s mock delay and
  the mic button's stub. Proved the wire end-to-end before adding
  intelligence — same milestone as the first Telegram echo test.
- Wired real mic capture (Web Audio API + MediaRecorder) streaming to
  Deepgram's live STT (nova-3, multilingual for English/Hindi) through
  the gateway, so the browser never holds the Deepgram key.
- Wired real TTS: `tts.py` proxies text to Deepgram's Aura-2, gateway
  returns MP3, frontend plays it. Full loop confirmed audible.
- Fixed a real bug: `voice_bridge.py` read `DEEPGRAM_API_KEY` from the
  environment at import time, before `main.py`'s `load_dotenv()` had run
  — made each new module self-sufficient (calls `load_dotenv()` itself)
  rather than depending on import order.
- Fixed a CORS bug: the TTS fetch (plain HTTP, unlike the WebSocket
  paths) was silently blocked cross-origin; added `CORSMiddleware` to
  `main.py` for the frontend's origin.
- Replaced keyword-match routing (`if "revenue" in text`) with real
  tool-calling via qwen2.5:7b through Ollama — confirmed working when
  "how are we doing on sales?" correctly routed to the pipeline tool
  despite containing none of the old trigger words.
- Found and fixed a real limitation: general/personal questions were
  going unanswered because tools bias small models toward always
  calling one. Split into two-tier routing — qwen2.5 (tools) decides if
  a report fits; llama3.1:8b (no tools) handles everything else.
- Wired two tools to real data: `get_usage_report` (queries `usage_events`
  via Supabase) and `get_catalog_report` (queries the `kb_keshri_pipes`
  Chroma collection ingest.py populates, with a real similarity search
  once the model extracts a search term — not just a static sample).
- Built continuous "Call" mode with barge-in: tap to start a persistent
  session, ask multiple questions without re-tapping, and Jarvis's
  speech now cuts off the instant new speech is detected mid-answer.
- Wrote `WORKING.md` — full architecture/flow reference for the voice
  pipeline (six-hop diagram, file map, real-vs-mock table, known gaps).
- Known gaps carried forward: four tools still fixtures, no conversation
  memory on this path, `tenant_id` hardcoded, `kb_keshri_pipes` /
  `kb_kesari_pipes` naming mismatch still unresolved.
- NEXT: wire remaining tools to real data, add conversation history
  threading, tenant-dynamic resolution.
