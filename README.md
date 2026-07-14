# Jarvis Core — Phase 0 → Live Deployment

This folder is the foundation of the multi-tenant agentic platform. It encodes the
architectural decisions that must be right on day one, so tenants 2–10 become
config rows instead of rewrites.

**Status as of 2026-07-10: live in production for one tenant (Kesari Pipes).**
Telegram text and Founder's Core voice are both deployed, unattended, on a
real VM + GPU pod. See `PROGRESS.md` for the session-by-session log and
`WORKING.md` for the voice pipeline's exact wiring.

**Status update, 2026-07-13:** **RunPod terminated.** Bot confirmed down
(direct message test, no reply) — production has been down, not just
degraded, and is staying down on purpose until the real fix, not a patch.

**The real fix, decided today:** production going down because one
compute provider disappeared means the gateway has zero resilience right
now. The fix isn't another single GPU — it's `main.py` and `founder_ws.py`
finally calling `llm_router.route()` for real (both currently bypass it
and hit Ollama directly — flagged since the first code review, urgent
now), with a `MODEL_MATRIX` that includes at least one free cloud
fallback (Groq — already confirmed working as an eval judge). Model
evaluation and acquisition is not a side project anymore; it's the
production reliability work. See PROGRESS.md 2026-07-13 for the full
decision log.

**Fix progress, same day (2026-07-13 evening session):** the fallback
half is built and certified. `llm_router.py` now carries free-cloud
chains (ollama → gemini → groq → openrouter → anthropic) **and a
certification gate**: it refuses to route to any (provider, model, task)
triple not marked green in the new `model_registry` table. First green
labels earned tonight — `gemini/gemini-flash-lite-latest` for intent
(100% accuracy) and `groq/llama-3.3-70b-versatile` for agent_turn
(tool-call format verified, 336ms). **What is still NOT done:** `main.py`
and `founder_ws.py` still bypass the router — the wiring step is the
remaining half of the production fix, so the bot is still down until
that lands.

**Note on "terminated":** if this was a true RunPod Terminate (not Stop),
the pod's persistent volume — including the three pre-pulled models — is
wiped, not just the running instance. Unconfirmed which actually
happened; assume a from-scratch model re-pull is needed on whatever GPU
comes next until proven otherwise.

**Status update, 2026-07-14: production healthy, 8/8 end-to-end eval passing.**
Both LLM paths are now off RunPod for real: `main.py` (07-13) **and**
`founder_ws.py` (07-14) route through Groq/Gemini fallback chains. Two live
retrieval bugs found via customer screenshots and fixed the same day —
exact product codes (KP005) now hit a deterministic metadata lookup before
semantic search, and "show me the full catalog" pulls all rows instead of
presenting the top-4 similarity hits as the whole catalog. Both are locked
in as regression cases in `eval_customer_bot.py`, an end-to-end eval that
exercises the REAL pipeline (retrieval + provider chain) with ground truth
parsed live from the tenant's Chroma collection — **8/8 passing on the
production VM**. Discipline going forward: run it after every deploy.

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
| LLM compute | ~~RunPod, pod `xl0rixu7dkzh1b`~~ **TERMINATED 2026-07-13** — bot confirmed down, not a patch job. If this was a true Terminate (not Stop), the persistent volume + pre-pulled models are gone too, unconfirmed. Real fix: route production through `llm_router.py` with a free-cloud fallback (Groq), not another single GPU. | Was 1x A40 (48GB VRAM), on-demand, NOT serverless. |
| Models on RunPod | `llama3.2:3b-instruct-q8_0`, `qwen2.5:7b-instruct-q8_0`, `mistral:7b-instruct-q8_0` | On the pod's persistent volume disk — survive stop/start, wiped only on Terminate. Same weights also used as eval candidates via the dslab tunnel — see Eval Engine section. |
| Database | Supabase (Mumbai region) | Unchanged from Phase 0. Also now holds `llm_evaluations` and `model_catalog` (eval engine, added 2026-07-12/13). |
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
**Updated 2026-07-13:** every task_type now has a free-cloud fallback
chain behind local, so a single compute provider disappearing (the RunPod
lesson) degrades service instead of killing it. The local Ollama entries
remain stale until the new GPU session — the cloud links in each chain
are what's real today.

| task_type | chain (first certified-green wins) | why |
|---|---|---|
| intent | llama3.2:3b (local, stale) → gemini flash-lite-latest 🟢 → groq llama-8b | runs thousands of times, must be ~free |
| agent_turn | qwen2.5:7b (local, stale) → gemini flash-latest 🔴* → groq llama-70b 🟢 → openrouter free → Claude Haiku | qwen proven at multi-tool calls; cloud chain covers GPU downtime |
| draft | mistral:7b (local, stale) → gemini flash-latest → groq llama-70b → Claude Sonnet | prose quality |
| escalation | Claude Sonnet (cloud, premium tier only) | hard reasoning |

\* contested red — see Certification gate below.

**The certification gate (new, 2026-07-13):** no (provider, model, task)
triple serves live traffic until `certify_model.py` marks it **green** in
`model_registry` (intent accuracy ≥90%, tool-call JSON format, safety
refusal probes — any safety miss is an automatic red — and a latency
ceiling per task). Red/uncertified = the router silently skips it, exactly
like a disabled `tenant_tools` row. Yellow = last-resort fallback only.
Every run is also archived in `eval_runs` so verdicts are auditable as
providers drift.

**Ordering rationale:** Gemini sits before Groq because its free tier
survives volume (~1M tokens/min on Flash-class vs Groq's 6–12K/min);
Groq is the speed fallback (336ms measured on the 70B). OpenRouter's
free pool is the last-resort net (independent underlying quotas).

**Gemini gotchas (hard-won 2026-07-13):** pinned dated model names like
`gemini-2.5-flash` return 404 "no longer available to new users" on new
`AQ.`-format keys — always use the rolling aliases `gemini-flash-latest`
/ `gemini-flash-lite-latest`. Flash and Flash-Lite have **separate**
free-tier quota pools, and the full Flash pool is tiny (~20 req/day
observed), which matters for both certification runs and live fallback.

## Eval Engine (Phase 0.5b, started 2026-07-12)
A separate, out-of-band system for grading candidate models BEFORE they get
promoted into `llm_router.py`'s `MODEL_MATRIX`. Not part of the production
request path — a bug in the eval engine cannot take down the Telegram
webhook or the founder voice pipeline.

**Important correction, made 2026-07-13:** this track started under the
wrong assumption that dslab was still production compute — it was retired
as production on 2026-07-10, two days before eval work began, in favor of
RunPod. **RunPod has since been formally abandoned** (see status note at
top of this file) after repeated unrecoverable GPU-reclaim failures.
dslab is once again the active compute — for local dev and eval work,
NOT for live production, which has no network path to reach it. A new GPU
provider is pending a separate future session.

**Judges:** Gemini (`gemini-flash-latest` — pinned dated names like
`gemini-2.5-flash` 404 on the newer `AQ.`-format Auth keys, must also use
the `X-goog-api-key` header not `?key=`) and Groq
(`llama-3.3-70b-versatile`) are both confirmed working. Anthropic is wired
but the key is currently invalid (401). Together.ai and NVIDIA NIM are
wired as candidate/judge options but unused — Together requires a $5
minimum deposit with no confirmed free tier live; NIM's model name is an
unverified guess, don't trust scores from it yet.

**Flow:** `generate` (candidate) → `tier1_rules` (local, free) → conditional
skip on hard-fail → `tier2_judge` (CRAFT: correctness, relevance, adherence,
faithfulness, tone) → `aggregate` → `persist` (Supabase `llm_evaluations`).
`catalog_from_run.py <run_id>` turns a completed run into a green/yellow/red
`model_catalog` row — manual today, the seed of a future button-driven flow.

**Results so far** (dslab, same model weights as RunPod's persistent volume
— relative rankings should transfer even though the infra path differs):
qwen2.5:7b-instruct 🟡 YELLOW (75-80%, cross-judged by both Gemini and
Groq — they independently agree on two real regression weaknesses),
llama3.2:3b-instruct 🔴 RED (55%), mistral:7b-instruct 🔴 RED (30%, Groq
only, no cross-check yet). None of these have been run against a real
production-matching pod yet since RunPod is abandoned — that gap gets
closed once the new GPU session happens, not before.

**Known gap:** `model_catalog` has a UNIQUE constraint on `(source,
model_name)` — a second eval run on the same model silently overwrites the
previous verdict. Qwen's dual-judge result currently only shows whichever
run was marked last; there's no way to see "both judges agree" from the
catalog table alone yet.

**Second certification track (added 2026-07-13 evening):**
`certify_model.py` + `model_registry`/`eval_runs` tables. This is the
router-enforced gate: unlike `model_catalog` (advisory, manual promotion),
`model_registry` is read by `llm_router.route()` at request time and
mechanically blocks uncertified models from live traffic. Per-task
verdicts (a model can be green for intent, red for agent_turn), full run
history in `eval_runs`, safety-probe failure = automatic red.
**Reconciliation needed:** two verdict stores now exist (`model_catalog`
from the CRAFT eval flow, `model_registry` from certify_model.py) —
long-term the CRAFT flow should feed `model_registry` as its persistence
layer, or one should absorb the other. Decide before Phase 1 closes.

**Certification results (2026-07-13):** gemini/flash-lite-latest 🟢 GREEN
for intent (100% on the 8-case grid incl. Hinglish, all refusal probes
passed, 1.3s); groq/llama-3.3-70b 🟢 GREEN for agent_turn (tool-call JSON
verified, 336ms); gemini/flash-latest 🔴 RED for agent_turn — **verdict
contested**: contaminated by 429s mid-run (Flash's ~20 req/day free pool
exhausted), re-certify after quota reset. Exposed a real eval-engine bug:
it cannot distinguish "model failed" from "provider throttled us" — both
land red. Fix: treat 429 as INCONCLUSIVE with backoff retry, never
convict on throttling.

**Files:** `eval_cases.py` (20-case test grid, Kesari-only, tenant-aware
refactor still pending), `eval_graph.py` (LangGraph), `eval_api.py`
(FastAPI orchestrator), `scorecard.py`, `catalog_from_run.py`,
`production_context.py`, `debug_judge.py` / `list_gemini_models.py`
(diagnostic tools — keep these, they're what found both Gemini bugs),
`eval_schema.sql`, `model_catalog_schema.sql`,
`model_catalog_add_signal.sql`, `compare_runpod_vs_dslab.py`,
`run_single_eval.py`.

See `PROGRESS.md` 2026-07-12 and 2026-07-13 entries for the full decision
log.

## Known gaps (see PROGRESS.md for full session detail)

- ~~**`get_catalog_report`'s similarity search unreliable**~~ **FIXED
  2026-07-14** — root cause was two-fold: embeddings can't distinguish
  product codes (KP005 ≈ KP001 to MiniLM), and the tool schema let the
  model send an empty query. Fix: exact-match metadata lookup
  (`where={"product_id": ...}`) before semantic search on BOTH paths
  (Telegram `main.py` + founder `founder_ws.py`), plus a required,
  strongly-described `query` parameter in the tool schema.
- **RunPod abandoned 2026-07-13** — repeated unrecoverable GPU-reclaim
  failures. Not being fixed; a new GPU provider is pending a separate
  future session. Don't spend more time troubleshooting this account.
- ~~**Production compute is currently broken**~~ **FIXED** — `main.py`
  (07-13) and `founder_ws.py` (07-14) both route through
  `llm_router.route()` / the Groq tool-calling chain now. No code path
  references the dead RunPod URL anymore. Local Ollama entries in the
  chains stay stale until the new GPU session.
- **Founder's Core's revenue/runway/pipeline tools are still mock
  fixtures** — there is genuinely no orders/deals/financial data to query
  yet (no such tables exist). `get_usage_report` (2026-07-14) is the
  template: real query → data summary → LLM phrases it, grounded, with
  `eval_usage_grounding.py` checking no number is ever invented.
  `get_briefing_report` is also real now (messages/users/moderation/stock).
- **Gateway memory pressure** — 740MB peak of the 1GB cap with swap in
  use after the embedding model loads (observed 2026-07-14). One more
  resident model or a traffic spike risks an OOM kill. Options: bigger
  droplet, or move embedding to a separate process/service.
- **No order-taking flow** — the bot correctly refuses to fabricate order
  confirmations (eval-enforced) and handles MOQ questions well, but there
  is no actual order capture. Ships behind a HITL gate per the original
  plan; demo framing: "coming next month."
- **No auth on `/ws/founder/*` or `/tts/*`** — fine while the URL is
  effectively private; needs a real gate before wider exposure.
- **Founder voice/text has no toleration middleware** — by design, per
  `founder_ws.py`'s own docstring (founder-only, not customer-facing).
  Telegram already has the real toleration/reputation system live.
- **The founder voice pipeline does not talk to the eval engine at all** —
  no tool queries `model_catalog` or `llm_evaluations`. Asking the founder
  HUD about eval results won't work until that tool is built (new work,
  not a connection fix).
- **`model_catalog`'s multi-judge overwrite gap** — see Eval Engine section
  above.
- **Two eval verdict stores** (`model_catalog` vs `model_registry`) — see
  Eval Engine section; reconcile before Phase 1 closes.
- **certify_model.py convicts on 429s** — throttling and genuine failure
  both land red. Add 429-aware INCONCLUSIVE + backoff retry, then
  re-certify gemini/flash-latest for agent_turn after its daily quota
  resets (midnight Pacific).
- **`schema.sql` is out of sync with live Supabase** — the `messages`
  table exists in the live DB but is missing from the file on disk
  (closes code_review.md item #1 once synced). Pull the actual live
  column definitions rather than guessing.
- **⚠️ Rotate `GEMINI_API_KEY`** — the full key appeared in pasted
  terminal logs during the 2026-07-13 session. Delete in AI Studio,
  create fresh, update `.env`. Do this before the next session ends.
- **OpenRouter unverified** — key authenticates (429 not 401 on first
  try) but the free pool was saturated; smoke-test again before counting
  it as a real link in the chain.
- **Chat-channel adapters still hand-rolled in Python** — Telegram's
  webhook is custom FastAPI code with its own payload parsing. Plan is to
  move this to n8n (see Phase Plan below) so adding WhatsApp/Slack/etc.
  is node configuration, not new Python files.
- **Products data lives only in Chroma text blobs** — prices/stock are
  baked into embedded documents; a price change means re-running ingest,
  and size/attribute queries ("1/4 inch pipe") have no structured lookup.
  Planned fix: a `products` table in Supabase as source of truth, with
  Chroma regenerated from it as a derived semantic index (two-path
  retrieval: SQL for exact entities, vectors for broad questions).

## Files
- `schema.sql` — the multi-tenant foundation (run against Postgres/Supabase)
- `toleration.py` — strike system with reputation-based limits (Telegram path only)
- `llm_router.py` — model matrix + free-cloud fallback chains + the
  certification gate (refuses non-green models; also the eval engine's
  provider layer)
- `providers.py` — uniform `call(prompt, timeout) -> (text, usage)`
  wrappers per provider (ollama, gemini, groq, openrouter, anthropic)
- `certify_model.py` — the certification gate's eval runner
  (green/yellow/red per model per task; safety miss = automatic red)
- `db_client.py` — shared Supabase client factory + tenant resolution
  (`resolve_tenant(slug)` — the single seam every channel now uses to
  turn a tenant_slug into a real tenant_id, tier, and chroma_collection)
- `schema_addition.sql` — `model_registry` + `eval_runs` DDL (already run
  against live Supabase 2026-07-13)
- `founder_ws.py` — founder tool registry + LLM tool-calling brain (voice AND typed chat)
- `founder_reports.py` — REST-path founder reports (real Supabase queries:
  usage, cost, switchbox, customers)
- `eval_customer_bot.py` — end-to-end customer bot eval: calls the REAL
  `ask_llm()` pipeline, ground truth parsed live from Chroma, both 07-14
  production bugs locked in as regression cases. Run after every deploy:
  `./venv/bin/python3 eval_customer_bot.py` on the VM.
- `eval_usage_grounding.py` — numeric-hallucination eval for the founder
  path's grounded `get_usage_report` (any number not in the real query
  result = fail)
- `voice_bridge.py` — mic audio ↔ Deepgram STT bridge
- `tts.py` — Deepgram TTS proxy
- `founders-core/` — primary live frontend
- `frontend/` — parked customer-facing frontend (Jarvis Command Hub)
- `WORKING.md` — the voice pipeline's exact architecture reference
- Eval engine files — see Eval Engine section above

## Phase Plan
- **Phase 0 (done):** local dev seed — one tenant, Telegram, local Chroma, toleration middleware.
- **Phase 0.5 (done):** real deployment — VM, RunPod GPU, live HTTPS, real voice pipeline for Founder's Core.
- **Phase 0.5b (in progress, started 2026-07-12):** eval engine — grade candidate models before MODEL_MATRIX promotion. See Eval Engine section.
- **Phase 1 (next, reordered 2026-07-13):** ~~build a `MODEL_MATRIX` with
  free-cloud fallback~~ **✅ done 07-13 evening** (gemini + groq certified
  green, certification gate live in the router). **Remaining, in order:**
  wire `main.py` and `founder_ws.py` through `llm_router.route()` for
  real — this is the actual production fix and the bot stays down until
  it lands; fix certify_model.py's 429-conviction bug + re-certify gemini
  flash for agent_turn; rotate the exposed Gemini key; reconcile
  `model_catalog` vs `model_registry`; provision + verify a new GPU
  provider (separate session, not blocking the above); fix the catalog
  tool-calling bug; point remaining founder tools at real data; add auth
  to the voice/founder routes; wire a model_catalog tool into the founder
  voice pipeline; migrate chat-channel adapters (Telegram now,
  WhatsApp/Slack/other later) from custom Python webhook code to n8n —
  Python keeps a single internal `POST /api/v1/chat`
  (tenant_id, channel, channel_user_id, display_name, text -> reply_text),
  n8n holds each channel's platform credentials itself and handles
  inbound payload parsing + outbound send via its built-in nodes, so a
  live secret never has to round-trip through Python on every message.
  Does NOT apply to `founder_ws.py`/`voice_bridge.py` — those stay custom
  Python; they're persistent WebSocket connections (full-duplex audio,
  barge-in) that n8n's request/response model can't hold open.
  `tenant_tools` stays the on/off switch per tenant/channel either way.
- **Phase 2:** Second tenant onboarded purely via config to prove isolation.
- **Phase 3:** B2C Life OS module — deferred deliberately, per original plan.

**Status update, 2026-07-13 (late night):** the wiring landed. `main.py`'s
Telegram path now calls `llm_router.route()` for real instead of hitting
Ollama/RunPod directly. `agent_turn` is temporarily restricted to
Groq/Gemini only (certified: groq/llama-3.3-70b-versatile green) until a
rented GPU cluster replaces RunPod. **Bot confirmed live and replying in
Telegram again.** `basic` tier temporarily allowed cloud (TIER_ALLOWS_CLOUD)
since local is down — revert once local inference is back and paid-cloud
tenants need the real gate.

**Status update, 2026-07-14:** the second half of the wiring landed too —
`founder_ws.py`'s tool-calling now walks a real fallback chain
(`TOOL_CALL_CHAIN`, currently Groq's llama-3.3-70b via the new
`providers.get_raw_chat_call` interface) and its text synthesis goes
through `llm_router.route()`. Tenant resolution is enforced end-to-end
(unknown slugs get a clean WS close, not tenant #1's data — which
surfaced and forced the fix of the kesari/keshri slug spelling mismatch
in the frontend, rebuilt + redeployed). Retrieval hardened (exact-match
codes, full-catalog intent), embedding model pre-warmed at startup, and
`eval_customer_bot.py` green at 8/8 against production.
