# Jarvis Core — Phase 0 → Live Deployment

This folder is the foundation of the multi-tenant agentic platform. It encodes the
architectural decisions that must be right on day one, so tenants 2–10 become
config rows instead of rewrites.

**Status as of 2026-07-10: live in production for one tenant (Kesari Pipes).**
Telegram text and Founder's Core voice are both deployed, unattended, on a
real VM + GPU pod. See `PROGRESS.md` for the session-by-session log and
`WORKING.md` for the voice pipeline's exact wiring.

## The One Rule
**`tenant_id` flows through everything** — every table, every Chroma collection,
every LangGraph thread ID, every usage log row. This is the difference between a
platform and a pile of scripts.

## Live infrastructure

| Piece | Where | Notes |
|---|---|---|
| Gateway (`main.py`) | DigitalOcean VM, `159.89.166.167`, systemd (`jarvis-gateway`) | Bangalore region. Survives reboots/crashes. |
| Founder's Core frontend | Same VM, systemd (`jarvis-frontend`), port 3000 | Real voice pipeline. Primary UI going forward. |
| Domain | `159.89.166.167.sslip.io` | Free magic-DNS, real Let's Encrypt HTTPS. Swap for a real domain later — one certbot re-run, no code changes. |
| Reverse proxy | nginx on the VM | Routes `/webhook`, `/health`, `/api/founder/*`, `/ws/founder/*`, `/tts/*` → gateway (:8000); everything else → frontend (:3000). |
| LLM compute | RunPod, pod `xl0rixu7dkzh1b`, 1x A40 (48GB VRAM) | On-demand pod, NOT serverless — start/stop manually between sessions to control cost. `ollama serve` currently a manual background process on the pod — **fragile, dies on session reset, needs converting to a real persistent service.** |
| Models on RunPod | `llama3.2:3b-instruct-q8_0`, `qwen2.5:7b-instruct-q8_0`, `mistral:7b-instruct-q8_0` | On the pod's persistent volume disk — survive stop/start, wiped only on Terminate. |
| Database | Supabase (Mumbai region) | Unchanged from Phase 0. |
| Voice STT/TTS | Deepgram (nova-3 STT, Aura-2 TTS) | Proxied through the gateway — browser never holds the API key. |

**Cost note:** the RunPod pod bills ~$0.44/hr while running, ~$0.017/hr while
stopped. **Always stop it between sessions** — a several-hour idle "running"
window is the single biggest avoidable cost in this stack.

## Two frontends, one gateway

- **`founders-core/`** — the business-owner HUD. **This is the primary,
  live UI.** Real voice in/out (mic → Deepgram STT → LLM tool-calling →
  Deepgram TTS), typed chat, barge-in support, report overlays
  (chart/gauge/table). See `WORKING.md` for the exact six-hop flow.
- **`frontend/`** ("Jarvis Command Hub") — customer-facing HUD, work in
  progress, parked for now. Has its own real voice wiring (`voiceClient.ts`)
  but hit an unresolved Deepgram-timeout bug (audio not reliably reaching
  the server) — not currently deployed.

Neither UI owns any logic. All routing, tool-calling, and data access
happens on the gateway — the UIs are thin clients.

## The Switchbox — how it actually works
MCP gives every tool the same plug shape. The tier toggle is **not** MCP itself —
it is the `tenant_tools` table. At session start, the client reads the enabled
rows for that tenant and mounts only those MCP servers. The Founder Dashboard is
CRUD on that table:

- Tenant upgrades to premium → flip `channel.whatsapp` to enabled, `channel.telegram` off.
- Enable `crm.gohighlevel` for a pro tenant → one row update.
- Agent code never changes. That is the whole trick.

## Model Routing
Compute moved from the dslab SSH tunnel to a RunPod pod — `OLLAMA_URL` in
`.env` is now the only thing that changed; `llm_router.py`'s fallback-chain
design meant nothing else needed touching. Same pattern applies to any
future compute swap.

| task_type | model | why |
|---|---|---|
| intent | llama3.2:3b (RunPod) | runs thousands of times, must be ~free |
| agent_turn | qwen2.5:7b (RunPod) → Claude Haiku (fallback) | qwen proven at multi-tool calls |
| draft | mistral:7b (RunPod) → Claude Sonnet (fallback) | prose quality |
| escalation | Claude Sonnet (cloud, premium tier only) | hard reasoning |

## Known gaps (see PROGRESS.md for full session detail)

- **`get_catalog_report`'s similarity search unreliable** — qwen2.5 often
  calls the tool without a search term, falling back to "show 8 generic
  products" instead of a targeted answer. Debug logging already added to
  `founder_ws.py` (`DEBUG tool call: ...` in the gateway logs) — check that
  first next session before guessing at a fix.
- **`ollama serve` on RunPod is not a persistent service** — needs a real
  startup script so it survives pod restarts without manual intervention.
- **Founder's Core's revenue/runway/pipeline/briefing tools are still mock
  fixtures** — same class of fix `founder_reports.py` already solved for
  the retired REST-based Founder's Core build. Point these at real
  Supabase queries once there's real business data to query.
- **No auth on `/ws/founder/*` or `/tts/*`** — fine while the URL is
  effectively private; needs a real gate before wider exposure.
- **Founder voice/text has no toleration middleware** — by design, per
  `founder_ws.py`'s own docstring (founder-only, not customer-facing).
  Telegram already has the real toleration/reputation system live.

## Files
- `schema.sql` — the multi-tenant foundation (run against Postgres/Supabase)
- `toleration.py` — strike system with reputation-based limits (Telegram path only)
- `llm_router.py` — model matrix + provider fallback chain
- `founder_ws.py` — founder tool registry + LLM tool-calling brain (voice AND typed chat)
- `voice_bridge.py` — mic audio ↔ Deepgram STT bridge
- `tts.py` — Deepgram TTS proxy
- `founders-core/` — primary live frontend
- `frontend/` — parked customer-facing frontend (Jarvis Command Hub)
- `WORKING.md` — the voice pipeline's exact architecture reference

## Phase Plan
- **Phase 0 (done):** local dev seed — one tenant, Telegram, local Chroma, toleration middleware.
- **Phase 0.5 (done, this session):** real deployment — VM, RunPod GPU, live HTTPS, real voice pipeline for Founder's Core.
- **Phase 1 (next):** fix the catalog tool-calling bug; make Ollama a real persistent service on RunPod; point remaining founder tools at real data; add auth to the voice/founder routes.
- **Phase 2:** Second tenant onboarded purely via config to prove isolation.
- **Phase 3:** B2C Life OS module — deferred deliberately, per original plan.
