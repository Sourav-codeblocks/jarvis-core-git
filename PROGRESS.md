# Jarvis Core — Progress Log

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
