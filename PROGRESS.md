# Jarvis Core — Progress Log

## 2026-07-05
- Supabase project 'jarvis-core' created, region Mumbai (ap-south-1)
- schema.sql executed successfully — all tables live, Kesari Pipes seeded as tenant 1
- RLS disabled in dev; revisit before prod clone
- Fixed tenant name spelling in DB: keshri-pipes (yaml file on disk still needs same fix)
- SUPABASE_URL + SUPABASE_SECRET_KEY + DB password all in .env

## 2026-07-06 — Session 1
- main.py created: FastAPI gateway with /health endpoint
- VERIFIED: gateway connects to Supabase Mumbai, returns live tenant data
- Docker-per-tenant deferred until multiple paying tenants

## 2026-07-06 — Session 2
- Telegram bot created: @Keshri_Pipes_Bot, token in .env
- Telegram webhook LIVE via ngrok tunnel (dev only, since replaced — see 07-10)
- FIRST LLM REPLY LIVE: ask_llm() via tunnel to dslab llama3.2:3b, persona working
- RAG GROUNDED: bot quotes KP001 @ Rs450 correctly, refuses to invent copper pipes
- usage_events logging live from row 1

<<<<<<< HEAD
## 2026-07-12 — Session 3: Eval Engine (infra decision + Phase 0.5 build)
- **New infra registered (not in codebase before today):**
  - RunPod — rented GPU, hosts CANDIDATE models under evaluation (vLLM/Ollama,
    OpenAI-compatible API assumed at /v1/chat/completions — unconfirmed, pod
    was down before we could verify, see below)
  - DigitalOcean VM — always-on orchestrator, no GPU. Runs the eval engine's
    FastAPI app (eval_api.py) as a SEPARATE process from main.py's gateway,
    deliberately out-of-band from production traffic.
  - dslab GPU (172.18.40.103, SSH tunnel) — unchanged, still production
    inference per main.py, now ALSO used as an eval candidate for comparison.
  - Anthropic + Gemini APIs — judge models only (Tier 2 CRAFT scoring), never
    the same provider as the candidate under test (llm_router.call_judge
    exclude_provider). Which judge is better is an open research question,
    swap order in llm_router.JUDGE_MATRIX.
- **Code review findings actioned** (see code_review.md):
  - llm_router.py: fixed uncaught KeyError on `providers[provider_name]` ->
    `.get()` with graceful fallthrough to next chain entry
  - eval_schema.sql's llm_evaluations table follows schema.sql conventions
    (tenant FK, TIMESTAMPTZ, BIGSERIAL) instead of a bespoke design
- **Eval engine architecture (two-tier, LangGraph):**
  generate (candidate, RunPod/dslab) -> tier1_rules (local, free) ->
  conditional skip -> tier2_judge (Anthropic/Gemini) -> aggregate -> persist
  (Supabase llm_evaluations)
- Files added: llm_router.py (extended), eval_cases.py (20-case grid, 5
  categories x 4), eval_graph.py, eval_schema.sql, eval_api.py,
  scorecard.py, compare_runpod_vs_dslab.py, run_single_eval.py
- Test grid includes 2 regression cases targeting KNOWN bugs from
  code_review.md: stale price after ingest update (content-hash dedup bug),
  wrong product category retrieval
- **INCIDENT: RunPod Community Cloud pod reclaimed** — "GPUs no longer
  available" on restart, "no instances currently available" for that GPU
  type/region. This is Community Cloud's known spot-reclaim tradeoff, not a
  one-off bug. Decision: retry with Secure Cloud tier next time; do NOT use
  "Start Pod using CPUs" fallback (too slow to be a meaningful eval
  candidate). Flagged for reconsideration once the $10 RunPod credit runs
  out — compare against Lambda Labs / Vast.ai / Modal before renewing.
- NEXT: run run_single_eval.py against dslab (llama3.2:3b-instruct-q8_0,
  matches production) to get the FIRST real scorecard — none exist yet, all
  of Phase 0.5 so far is infrastructure with zero actual eval data collected.
  Once RunPod is back: compare_runpod_vs_dslab.py for the real comparison.
  Then: cron on the DO VM for the Sunday scheduled run (not yet configured).

## 2026-07-13 — Session 4: First real scorecards, Gemini fixed, RunPod abandoned, discovered the founder voice pipeline
- **Bug fixed:** eval scripts defaulted `--tenant-slug` to `kesari-pipes`
  (matching schema.sql's literal text) instead of `keshri-pipes` (the actual
  DB value per the 2026-07-05 spelling fix, and what main.py hardcodes).
  Fixed defaults in run_single_eval.py, compare_runpod_vs_dslab.py,
  eval_api.py. This is the same unresolved spelling inconsistency
  code_review.md #4 flagged — still not fixed at the source
  (schema.sql / tenant.kesari.example.yaml still say "kesari").
- **Gemini judge fixed, two separate bugs:**
  1. New `AQ.`-format "Auth key" (replacing the old `AIzaSy...` "Standard
     key" format) must be sent via `X-goog-api-key` HEADER, not `?key=`
     query param. The query param happened to work for the read-only
     `models.list` endpoint but 404'd on `generateContent`.
  2. Even with the header fixed, the pinned model name `gemini-2.5-flash`
     still 404'd. Auth-format keys appear scoped to the rolling `-latest`
     aliases only. Fixed by switching to `gemini-flash-latest`.
  Both fixes are in `llm_router.py`. Confirmed working via `debug_judge.py`.
- **Groq confirmed as a fully working judge** — `llama-3.3-70b-versatile`,
  free tier, no issues since first use.
- **Anthropic still 401 Unauthorized** — key format looks structurally
  valid (correct `sk-ant-` prefix, correct length, no stray characters),
  so this is likely a genuinely invalid/unactivated key, not a paste error.
  Deferred, not blocking anything.
- **Together.ai investigated, NOT adopted today:**
  - No free trial credits currently offered (per their own docs) — a
    mandatory minimum $5 deposit is required before ANY API call works,
    confirmed directly via the dashboard's "read-only mode" banner.
  - `Qwen2.5-7B-Instruct-Turbo` confirmed NOT free: $0.30/1M tokens.
  - `Gemma-4-31B` has no serverless/pay-per-token pricing at all —
    Dedicated-endpoint only (billed per GPU-hour, same cost model as
    RunPod). Blank pricing on their model page means "can't call this
    casually," not "free."
  - Provider code (`make_together_provider`) is written and wired into
    `llm_router.py`, but UNUSED — no deposit made, no real call attempted.
  - Decision: skip Together for now. Revisit only if a specific model
    there is worth the $5, not as a default path.
- **NVIDIA NIM added to the router, also UNUSED today** —
  `make_nim_provider` written, registered as both a candidate and judge
  option, but the model name (`meta/llama-3.1-70b-instruct`) is an
  UNVERIFIED GUESS — same mistake that cost an hour on Gemini. Do not
  trust a NIM-judged score until this is confirmed against NVIDIA's real
  catalog the way `list_gemini_models.py` did for Gemini.
- **RunPod: DECISION — abandoned for this account.** Checked repeatedly
  across the session; GPU reclaim persists every time ("no instances
  available"). Not treating this as "try again later" anymore.
  - **Using dslab exclusively as the local-model source until IIT Mandi
    lab access ends July 18.**
  - **BACKLOG, do after July 18:** evaluate a real replacement (Secure
    Cloud RunPod / Lambda Labs / Vast.ai / Modal — compare before
    committing), provision it, THEN cancel the current RunPod account
    entirely. Don't run both — kill the old one once the new one works.
- **model_catalog table extended** (`model_catalog_add_signal.sql`):
  added `signal` (green/yellow/red), `pass_rate`, `eval_run_id`,
  `last_evaluated_at` columns; widened the `source` CHECK constraint to
  include `together_ai`.
- **`catalog_from_run.py` built** — takes a `run_id`, computes stats via
  `scorecard.compute_stats()` (refactored out of `scorecard.py` so both
  the human-readable report and the catalog use identical signal logic,
  never two copies that could drift), upserts a `model_catalog` row.
  This is the manual seed of the "run tests via button" roadmap item —
  same underlying operation, triggered by hand for now.
- **REAL eval data exists for the first time — three dslab models
  marked in model_catalog:**
  | Model | Pass rate | Signal | Judge(s) |
  |---|---|---|---|
  | llama3.2:3b-instruct-q8_0 | 55% | RED | Groq (single) |
  | mistral:7b-instruct-q8_0 | 30% | RED | Groq (single) |
  | qwen2.5:7b-instruct-q8_0 | 75% (Groq) / 80% (Gemini) | YELLOW (both) | Groq + Gemini (cross-checked) |
  - Qwen cross-judge check: both judges independently agree on the two
    real regression weaknesses (`regression_language_mixing_bug`,
    `regression_over_refusal_valid_query` both fail on both judges) —
    that's judge-independent signal, trust it. Where they disagree
    (3 cases, mostly adversarial/boundary) is expected judge noise,
    consistent with the ~20% disagreement rate seen on llama3.2 earlier.
  - **KNOWN GAP, not yet fixed:** `model_catalog` has a UNIQUE constraint
    on `(source, model_name)` — running `catalog_from_run.py` a second
    time on the same model SILENTLY OVERWRITES the previous verdict.
    Qwen's catalog row currently reflects whichever run was marked last;
    there's no way yet to see "both judges agree on YELLOW" from the
    catalog table alone, only from this log / the raw `llm_evaluations`
    rows. Needs a real design fix (e.g. store best-of/most-recent-N runs,
    or a separate `model_catalog_judge_scores` table) before the catalog
    can be trusted as the single source of truth on its own.
  - mistral has only ONE judge's read (Groq) — no Gemini cross-check yet,
    unlike qwen. Its RED signal is less independently confirmed.
- **DISCOVERED (not built this session): a second, already-live system —
  the Founder Voice Pipeline.** Fully documented in `WORKING.md`, which
  existed before today but was never connected to this thread until now.
  Summary, see `WORKING.md` for the real detail:
  - Two frontends: `frontend/` (customer HUD) and `founders-core/`
    (founder HUD, voice + typed chat), both thin clients over `main.py`.
  - Real pipeline: browser mic -> `voice_bridge.py` -> Deepgram (nova-3
    STT) -> `founder_ws.py`'s `route_founder_query()` -> `qwen2.5:7b` via
    Ollama/dslab tool-calling -> real tool function -> Postgres/ChromaDB ->
    spoken answer -> Deepgram Aura-2 TTS -> browser.
  - Live at https://159.89.166.167.sslip.io/ (DO VM) and
    https://github.com/Sourav-codeblocks/jarvis-core-git (this answers
    the "is there a GitHub remote" question from 2026-07-12 — yes).
  - Of six founder tools, only `get_usage_report` and `get_catalog_report`
    are real (query Supabase/ChromaDB); `get_revenue_report`,
    `get_runway_report`, `get_pipeline_report`, `get_briefing_report` are
    MOCK FIXTURES. This matches exactly what's visible on the live HUD's
    "REPORTS" panel (Revenue/Runway/Pipeline/Briefing) — confirmed by
    fetching the live page and cross-referencing `WORKING.md`.
  - **This pipeline does NOT yet talk to the eval engine at all.** No
    tool queries `model_catalog` or `llm_evaluations`. Asking the founder
    HUD about eval results today will not work — there's nothing wired.
  - `WORKING.md`'s own documented gaps (not new findings, just surfacing
    them here since they're relevant to eval work too): tenant_id
    hardcoded to 1 in this path too (same fix as main.py's, not yet
    done); `route_founder_query()` calls Ollama directly, bypassing
    `llm_router.py` entirely; no `usage_events` logging for founder
    queries; the `kb_keshri_pipes` vs `kb_kesari_pipes` Chroma name
    mismatch (code_review.md #4) persists here too.
- **NEW WORKING CONVENTION, starting today:** update BOTH README.md and
  PROGRESS.md at the end of every session, not just PROGRESS.md.
  COMMANDS.md's "End a session" checklist updated to say so explicitly.
- NEXT:
  1. Fix the model_catalog multi-judge overwrite gap (design decision
     needed: aggregate table vs. most-recent-wins vs. something else)
  2. Cross-check mistral against Gemini too (currently Groq-only)
  3. Add a `model_catalog` tool to the founder voice pipeline's tool
     registry so "how did qwen do on evals" becomes a real, answerable
     voice query — NOT built yet, this is new work, not a connection fix
  4. Verify NIM's actual model catalog before trusting any NIM-judged or
     NIM-candidate score (same discipline as `list_gemini_models.py`)
  5. Tenant-aware refactor of `eval_cases.py` / `production_context.py`
     (still Kesari-only, flagged 2026-07-12, still not started)
  6. After July 18: kill RunPod, provision + verify a real replacement
     GPU source
=======
## 2026-07-08
- Built real voice pipeline locally (not yet deployed): `founder_ws.py`
  (LLM tool-calling brain), `voice_bridge.py` (mic → Deepgram STT bridge),
  `tts.py` (Deepgram TTS proxy)
- Built `founders-core/` frontend — real mic capture, barge-in, continuous
  call mode (`voice.ts`'s `startVoiceSession()`)
- All of the above stayed local-only — never pushed to git, never deployed.
  Found and fixed this gap on 07-10 (see below).

## 2026-07-10 — Session 3: production deployment (the big one)

**Infrastructure — from zero to permanently live:**
- Evaluated Hetzner (rejected — documented India-signup rejection pattern),
  Railway (rejected — usage-based billing less predictable than needed),
  DigitalOcean settled on: $6/mo droplet, Bangalore region, Ubuntu 24.04
- VM provisioned: `159.89.166.167`, SSH key auth
- `bootstrap_vm.sh` run: nginx, certbot, systemd service (`jarvis-gateway`),
  firewall — all in one pass
- Domain: `159.89.166.167.sslip.io` (free magic-DNS), real Let's Encrypt cert
- **ngrok fully retired** — permanent HTTPS URL, no more rotating tunnel URLs

**Compute — moved off dslab:**
- RunPod pod deployed: `xl0rixu7dkzh1b`, 1x A40 (48GB VRAM), $0.44/hr running
  / $0.017/hr stopped, 60GB persistent volume disk
- Template: "pytorch and ollama - persistent workspace" (chosen specifically
  so the volume survives stop/start — container disk alone does not)
- Three models pulled: `llama3.2:3b-instruct-q8_0`, `qwen2.5:7b-instruct-q8_0`,
  `mistral:7b-instruct-q8_0`
- `main.py`'s `OLLAMA_URL` made configurable via env var — swapping compute
  providers is now a one-line `.env` change, no code touches needed
- **Known fragility:** `ollama serve` was started manually in RunPod's Web
  Terminal — not a persistent service. Died twice tonight when the pod was
  stopped/restarted or the terminal session reset. Real fix (a startup
  script) still needed — see README.md gaps.

**Bugs found and fixed during deployment (all from local-only files never
having been uploaded/tested against the real stack):**
- `founder_ws.py` was importing itself before it existed on the VM —
  `ModuleNotFoundError` chain across `founder_ws.py`, `voice_bridge.py`,
  `tts.py` — all three were real, working code that had just never been
  uploaded. Fixed by uploading and uncommenting the disabled imports.
- `.env` corruption from a `cat >>` with no trailing newline on the prior
  file — two vars silently concatenated onto one line. Fixed by rewriting
  the whole file cleanly.
- `chroma_db/` collection missing on the VM (only the code was uploaded,
  not the ingested vector data) — copied over from the Mac.
- Typing indicator added to the Telegram path (`sendChatAction` ping loop)
  — Telegram doesn't show this automatically, has to be triggered.
- `founder_ws.py` had `OLLAMA_URL` hardcoded to `localhost:11434` and
  `CHAT_MODEL = "llama3.1:8b"` (a model never pulled) — both fixed to match
  the real RunPod setup.

**Frontend — Founder's Core deployed as the primary live UI:**
- Confirmed via git-clone + local Mac comparison: the real voice-wired
  `founders-core/` (built 07-08) was never pushed to git and never
  deployed — only existed on the Mac. The `Founder's Core.zip` Lovable
  export tested earlier tonight was a different, older, non-voice version
  — source of significant confusion mid-session.
  `Jarvis Command Hub` (`frontend/`) was deployed first, real mic wiring
  built from scratch (`voiceClient.ts`), got as far as the VM + systemd +
  nginx — then parked in favor of `founders-core/` once its existence was
  discovered. Command Hub's own voice hit an unresolved Deepgram-timeout
  bug (audio not reliably reaching the server) — worth revisiting later,
  not urgent since Founder's Core is now primary.
- Discovered TanStack Start's Nitro build defaults to `preset:
  cloudflare-module` (Cloudflare Workers target) via the shared Lovable
  config wrapper — silently produces a non-runnable-on-plain-VM output.
  Fixed with `NITRO_PRESET=node-server bun run build` — same fix applies
  to any Lovable/TanStack Start project deployed this way.
- Both `dataAdapter.ts` and `voice.ts` had `localhost:8000` hardcoded —
  patched to use `VITE_GATEWAY_URL`, matching the pattern used everywhere
  else tonight.
- Build had to happen on the Mac, not the VM — the $6/mo droplet's 1GB RAM
  couldn't complete the build (thrashing, no swap). Added a 2GB swap file
  to the VM regardless, as insurance against future memory pressure.
- Deployed as its own systemd service (`jarvis-frontend`, port 3000);
  nginx routes by path — known API routes to the gateway, everything else
  to the frontend — so both share one domain and one cert.

**End-to-end confirmed working tonight:**
- Telegram: real conversational replies, RAG-grounded, typing indicator, 200 OK throughout
- Founder's Core voice: mic → live transcript → LLM tool-calling → spoken
  reply, confirmed multiple times including `get_usage_report` (real
  Supabase data) via voice

**Known bug, not fixed tonight:**
- `get_catalog_report` — asking about specific products returns the
  generic "showing 8 products" fallback instead of a targeted search.
  Debug logging added to `founder_ws.py`'s tool-call handling
  (`DEBUG tool call: name=... args=...` in gateway logs) but the actual
  fix wasn't reached before ending the session. **Check that debug output
  first thing next time** — it'll show immediately whether qwen2.5 is
  failing to extract the search term or something else is wrong.

**Housekeeping:**
- `founder_ws.py`, `voice_bridge.py`, `tts.py`, and `founders-core/` all
  pushed to git for the first time tonight — previously existed only
  locally and on the VM. Git now actually reflects reality.

**NEXT:**
1. Fix `get_catalog_report`'s tool-calling (debug logging already in place)
2. Convert `ollama serve` on RunPod into a real persistent service
3. Test barge-in properly (interrupt Jarvis mid-sentence, confirm it stops)
4. Point remaining founder tools (revenue/runway/pipeline/briefing) at real data
5. Add auth to `/ws/founder/*` and `/tts/*` before any wider exposure
6. Revisit Jarvis Command Hub's Deepgram-timeout bug once Founder's Core is solid
>>>>>>> 0a01ef885a09db033cc4ebce2b8e909e59bc8c95

## 2026-07-13 — Cloud fallback onboarding + certification gate
- Context: dslab GPU/Ollama not always reachable — onboarded free-tier cloud models as fallback
- NEW: model_registry + eval_runs tables live in Supabase (schema_addition.sql) — the certification gate
- NEW: certify_model.py (eval engine job #1) — intent accuracy, tool-call format, safety refusal probes, latency; verdicts green/yellow/red; safety failure = automatic red
- NEW: providers.py (uniform call wrappers: ollama/gemini/groq/openrouter/anthropic), db_client.py (shared supabase factory)
- UPDATED: llm_router.py — fallback chains now ollama → gemini → groq → openrouter → anthropic; router refuses to route to anything not green in model_registry
- Gemini gotcha: gemini-2.5-flash retired for new accounts → use rolling aliases gemini-flash-latest / gemini-flash-lite-latest (never breaks on retirement)
- CERTIFIED GREEN: gemini/flash-lite-latest for intent (100% accuracy, 1.3s), groq/llama-3.3-70b for agent_turn (tool calls OK, 336ms!)
- RED (contested): gemini/flash-latest for agent_turn — verdict contaminated by 429s (flash daily quota ~20 req, separate from flash-lite pool); re-certify after quota reset
- EVAL ENGINE BUG FOUND: can't distinguish "model failed" from "provider throttled" — both land red. Fix next session: treat 429 as INCONCLUSIVE + backoff retry
- OpenRouter: key authenticates, free pool 429'd on first try — retry later
- NOTE: messages table already EXISTS in live Supabase but is missing from schema.sql on disk — sync schema.sql to match reality (closes code_review.md item #1)
- ⚠️ SECURITY: rotate GEMINI_API_KEY (full key appeared in pasted terminal logs) — delete in AI Studio, create new, update .env
- NEXT: re-certify gemini flash for agent_turn after quota reset; add 429-aware retry to certify_model.py; sync messages table into schema.sql

## 2026-07-13 — Session 3 (evening, cont'd)
- Tenant-dynamic resolution files (db_client.py, main.py, founder_ws.py,
  voice_bridge.py) copied into working tree from Claude-generated patch,
  originals backed up to .backup_pre_tenant_fix/. TENANT_SLUG=keshri-pipes
  added to .env.
- INTERRUPTED MID-DEPLOY — got pulled into n8n architecture discussion
  before finishing. Current state of these 4 files: NOT syntax-checked,
  NOT committed, NOT pushed. founder_reports.py stub NOT yet created
  (main.py will crash on import without it). Gateway NOT restarted —
  moot anyway since production is separately down (RunPod terminated,
  see status note at top of README).
- Decided: chat-channel adapters (Telegram now, WhatsApp/Slack later)
  will move to n8n eventually — Python keeps a thin POST /api/v1/chat,
  n8n owns platform credentials + payload parsing. Documented in
  README.md Phase Plan + Known Gaps, committed + pushed (067ec6b).
  This does NOT apply to founder_ws.py/voice_bridge.py (stay custom
  Python — persistent WebSocket, n8n can't hold that open).
- NEXT: finish the tenant-resolution deploy — py_compile the 4 files,
  create founder_reports.py stub, restart gateway, verify via Telegram
  message + /health, THEN commit+push. Do this before starting the
  actual production fix (llm_router.route() wiring into main.py /
  founder_ws.py) so the two changes don't get tangled in one commit.

## 2026-07-13 — Session 4 (late night) — production restored
- Finished the tenant-resolution deploy from earlier tonight (db_client.py
  was missing resolve_tenant/UnknownTenant on the VM; added, deployed, verified)
- Wired main.py's ask_llm() to llm_router.route() -- replaces the dead
  RunPod call. agent_turn temporarily Groq+Gemini only (ollama_local/
  openrouter/anthropic_api removed from this chain only until local GPU
  cluster is ready)
- TIER_ALLOWS_CLOUD: basic temporarily allowed cloud (was local-only) --
  revert once local is reliable again
- CONFIRMED: real Telegram message -> Groq reply -> correct catalog
  grounding, end to end, live on the VM
- NEXT: wire LLM to product_catalog properly + eval testing against real
  DB queries; re-certify gemini/flash-latest for agent_turn after quota
  reset; revert the two TEMP gates once local GPU cluster is up

## 2026-07-14 — Session (4:00 PM – 5:10 PM)
- KP005 retrieval bug fixed: exact-match metadata lookup before semantic search (embeddings can't distinguish product codes)
- Full-catalog bug fixed: list-everything intent detection pulls all rows (capped 50), English + Hinglish patterns
- Embedding model pre-warmed at gateway startup — HF cold start no longer lands on first customer question
- eval_customer_bot.py: 8-case end-to-end eval, REAL pipeline (retrieval + Groq), ground truth parsed live from Chroma — 8/8 PASSING on production VM
- Eval calibration lesson: category check originally failed a genuinely good broad answer; recalibrated (broad Qs deserve broad As)
- Discipline going forward: run eval_customer_bot.py after every deploy; add every production breakage as a regression case
- NEXT: demo script for Jul 26 (freeze features, rehearse against prod) OR products table in Supabase (structured truth for prices/stock; Chroma becomes derived index)
