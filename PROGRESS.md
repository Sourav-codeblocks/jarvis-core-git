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

## 2026-07-23 — Session: droplet git bootstrap, order-guardrail fix, owner-role tools
- **Tier 0 done**: droplet had NO git history at all until today. Initialized,
  reconciled against the stale GitHub `main` (which still had the whole
  frontend/eval-engine tree that was never actually deployed here), pushed
  the droplet's real running state as a new branch `droplet-live`. Going
  forward: commit after every real change, not just `cp file file.bak`.
- **Real production bug found + fixed**: Telegram bot was confirming
  fictional orders (tested live: "place 100 pieces of Teflon Tape" got a
  fabricated success message with a fake total and fake follow-up promise).
  Root cause: `main.py`'s system prompt forbade inventing facts but never
  said it couldn't confirm an order. Fixed by adding an explicit
  no-order-confirmation rule; later widened to cover ANY action (forward,
  send, dispatch), not just orders, after the same failure mode showed up
  on vendor-forwarding and festival-greeting requests (both were pure
  narration — neither tool existed yet at the time).
- **Full-catalog regex gap found, not yet fixed**: "pura product list dena"
  and "pura samaan ka list do" don't match `FULL_CATALOG_PATTERNS` — the
  regex only catches "pura" directly followed by "catalog/list," not
  natural phrasing with words in between. Queued, not fixed tonight.
- **Hindi TTS root cause found, not yet fixed**: `tts.py` hardcodes an
  English-only Deepgram Aura voice (`aura-2-helena-en`). Explains "garbled
  Hindi speech" reported on the founder voice path. Needs a Hindi-capable
  voice or a language-aware TTS branch. Queued, not fixed tonight.
- **RBAC discovery**: found an existing, more complete identity system
  (`identities` + `channel_links`, admin/founder/staff roles, multi-channel
  linking) already migrated on 2026-07-14 but never wired to any code —
  fully dead, zero rows in `channel_links` until tonight. Decision: use
  THIS as the real system going forward (not the `users.role` column added
  earlier tonight, which is now superseded/unused for authorization).
  Seeded: Sourabh = admin, Nikunj Goel = founder, both linked to real
  Telegram chat IDs.
- **New: `owner_tools.py`** — channel-abstraction (`send_channel_message`,
  Telegram real/WhatsApp stubbed so a future channel swap is one function),
  `resolve_identity_role()` (checks `channel_links`→`identities`), and the
  first real owner tool: `forward_to_vendor()`. Deterministic result text
  decided in code from a real delivery attempt — the LLM narrates nothing,
  closing the same class of bug as the order-confirmation fix.
- **New: `vendors` table** — tenant-scoped, loose category matching.
  Seeded Sourabh as a `cement` test vendor to validate end-to-end without
  a real vendor yet.
- **`main.py` wired**: resolves identity on every Telegram message: if
  admin/founder, tries the owner tool-calling layer first (Groq raw
  tool-calling, same proven pattern as `founder_ws.py`) before falling
  back to the normal grounded reply. Also added a role-aware persona split
  — owners get a warm personal-assistant tone, never a "Portal active,
  telemetry: X" dashboard voice; customers keep the existing tone.
- **CONFIRMED LIVE, working end-to-end**: "send 550 bori of cement to
  nagesh in kota, forward this message to vendor" → correct extraction
  (customer, quantity, item, location) → real Telegram delivery to the
  seeded test vendor → correct, non-hallucinated confirmation text.
- **Known gap re-surfaced, not new**: `get_recent_history()`'s 8-message
  window meant asking "did that work?" a few turns after a successful
  forward got an honest-but-wrong "I don't have confirmation" — the real
  confirmation had scrolled out of context. Same conversation-memory gap
  already tracked; not a regression from tonight's work.
- **Not yet tested**: `forward_to_vendor` when NO vendor exists for the
  requested category (e.g. "steel" — nothing seeded). Should hit the
  honest "couldn't find a vendor" path in `find_vendor()`. Worth
  confirming before Nikunj/Gaurav use this live.
- NEXT: test the no-vendor-found path; fix the full-catalog regex; fix
  Hindi TTS voice; get Rajesh Bhai's real Telegram ID and seed him as the
  real cement vendor (currently just Sourabh as test vendor); rehearse
  demo script for Jul 26.

## 2026-07-26 — Session: Mihika's Studio onboarded, droplet resized, Docker/architecture correction

**Droplet infrastructure:**
- Resized droplet 1GB→2GB RAM, 1→2 vCPU, 25GB→60GB disk (was already
  swapping under just Keshri Pipes alone before this — real, not
  precautionary). `MemoryMax` on jarvis-gateway.service raised 1G→1.5G to
  match; was capping the service at the OLD machine's ceiling even after
  the host itself had more room.
- Second tenant deployed as a SEPARATE folder/venv/systemd service
  (`/opt/jarvis-core-mihika`, `jarvis-gateway-mihika.service`, port 8001)
  — NOT a shared process. Correctly identified mid-session that "one
  process serves every tenant" would trade file-duplication pain for
  crash-blast-radius risk (one tenant's bug taking down every tenant's
  bot) — wrong trade. **Real fix, not done tonight, scoped for a future
  session: Docker.** Build the shared code once as an image, run each
  tenant as an isolated container from it — keeps process isolation,
  eliminates the "did I copy this fix to every folder" risk that bit us
  twice tonight (see below).
- nginx: added a path-based route (`/mihika/webhook/telegram` → rewritten
  → port 8001) so both tenants' Telegram webhooks share one domain/cert.

**Mihika's Studio — first real second tenant, end to end:**
- Real business data used: Google Business listing (site itself and the
  share.google link both block automated fetching via robots.txt) —
  address, phone, hours (11am-8:30pm, 7 days, matches what was already
  told), 4.8/136 reviews, real service categories. Company profile
  written from this, paraphrased (never verbatim, copyright discipline).
- Booking template (Layer 2, reusable for any future time-slot business):
  `services`, `resources`, `resource_schedules`, `bookings`,
  `premium_customers`, `booking_feedback` tables. `booking_tools.py`:
  availability engine (validated directly against real seeded data —
  correct slot math, correct break-time buffer exclusion, confirmed via
  direct test scripts before ever touching a live bot), deterministic
  (code-decided, never LLM-narrated) booking creation, artist
  notification on successful booking (reuses `owner_tools.send_channel_message`
  — same function that will make WhatsApp support universal later).
- Real services replaced placeholders (Haircut/Spa/Facial/Bridal ->
  Haircut & Styling, Hair Coloring, Threading, Waxing, Makeup x2 tiers,
  Manicure, Pedicure, Nail Art) — durations/prices still ESTIMATED, no
  public rate card exists; names/categories are real.
- Premium/non-premium artist-choice split: enforced in CODE (two
  different tool schemas — non-premium's book_appointment has no
  resource/artist parameter AT ALL), not just prompted.

**Real bugs found and fixed, in order:**
1. Owner persona repeated the founder's name in literally every reply —
   root cause: name injected into the system prompt every turn with no
   "use sparingly" instruction. Fixed; then found the fix over-corrected
   to NEVER using the name — flagged as needing real few-shot examples
   later, not another one-line tweak (deferred deliberately).
2. Booking-enabled tenant's `ask_llm()` crashed on ANY non-booking
   message — assumed every tenant has a ChromaDB collection; Mihika's
   Studio deliberately has none (too few services to need vector search).
   Fixed: booking-enabled tenants read `services` table directly instead
   (`booking_tools.build_services_catalog_text`).
3. `main.py`'s hardcoded fallback business description was literally "a
   wholesale supplier" (Keshri Pipes-specific) — leaked into Mihika's
   identity ("We're a wholesale supplier and salon...") because
   `tenants.business_desc` was never set for her. Fixed the immediate
   case AND the fallback default (now generic "a local business") so the
   next tenant that forgets this column doesn't inherit wrong industry
   text either.
4. **Cross-tenant identity leak, the most serious find tonight**:
   `resolve_identity_role()` looked up a Telegram account with NO tenant
   filter — meaning an admin identity created for Keshri Pipes was being
   applied on Mihika's bot too, purely because it's the same person's
   Telegram account. Fixed with a tenant-scoped `!inner` join filter.
   Root cause of the "vague, evasive, oddly owner-toned" replies a
   customer-role tester was getting on Mihika's bot.
5. `check_availability`/`book_appointment` crashed the whole request on
   any date the model phrased in words instead of YYYY-MM-DD ('today',
   then later 'current date' — proving word-matching alone isn't enough).
   Fixed with `_normalize_date()` for the common cases AND a real
   try/except around tool execution so ANY malformed input degrades to
   an honest reply instead of a 500 — the actual fix, not just patching
   individual words.
6. Missed booking intent: "Haircut for tomorrow please" has no keyword
   match, silently fell through to plain chat. Fixed by removing the
   keyword pre-filter for booking-enabled tenants entirely (always try
   the real tool-decision call — cheap, low-volume tenants, worth it to
   never miss a real booking).
7. That fix's own regression: removing the keyword gate made the tool
   fire TOO eagerly on ambiguous short questions ("Waxing?", "Hair
   color?") and on multi-service mentions ("hair color and waxing"
   mangled into one unmatched string). Tightened the tool-decision system
   prompt with explicit negative examples. Improved, confirmed on the
   compound-service case; NOT fully solved (see open item below).

**Confirmed working end-to-end tonight:**
- Vendor forwarding (Telegram, real delivery, deterministic confirmation)
- Single-message bookings with complete info
- Ambiguous compound-service question now gets a proper clarifying reply
- Cross-tenant identity isolation

**Known gap, NOT solved tonight — real, structural, not a quick fix:**
Multi-turn booking narrowing ("show me times" -> "4pm" -> should book)
is unreliable. The tool-decision model keeps re-calling
`check_availability` instead of transitioning to `book_appointment` once
a customer has clearly narrowed to one slot. Conversation history is now
passed in (fixed a related bug), but inferring "what stage of the booking
flow are we at" purely from raw history each turn is fundamentally
fragile. Real fix likely needs explicit conversation-state tracking
(e.g. "last shown: service X, date Y — next input is a time"), not
another prompt tweak. Scoped as a real next task, not attempted further
tonight given diminishing returns from live prompt iteration at this hour.

**Also found tonight, unrelated to Mihika:** twice made the same mistake
editing `booking_tools.py` via `str_replace` — old_str matched only a
function's signature line, deleting the whole body underneath. Caught
both times via explicit post-edit verification (checking every expected
function name still exists via `ast.walk`), not just a syntax check —
worth keeping that habit for any future multi-function file edit.

**NEXT:**
1. Design real conversation-state tracking for the booking flow (the
   open item above)
2. Docker: shared image, per-tenant containers — replaces the
   copy-every-file-twice pattern this session exposed as fragile
3. Confirm real service durations/prices with Mihika directly
4. Seed Rajesh Bhai as the real cement vendor (still only Sourabh as
   test vendor)
5. Gaurav not yet seeded as a founder identity — no Telegram ID on file
6. `founder_reports.py` still stale (hardcoded TENANT_ID=1) — unrelated
   carryover from before, still unfixed
7. Improve the "wall of comma-separated times" availability format —
   noted as low-priority by design call, not forgotten

## 2026-07-26 (continued, part 3) — Live outage during a real demo, provider quota crunch, demo tenant built

Continuation of the same extended session. Parts 1 and 2 (above) cover
the droplet resize, the booking engine build, and the first fallback
chain. This part covers what happened once real demo traffic hit it.

**Real incident: both bots went down mid-demo.** Root cause, in order:

1. Groq's free-tier DAILY token cap (100,000 TPD) got fully exhausted —
   not from malicious load, just from the sheer volume of real testing
   plus real demo traffic in one evening. Confirmed via Groq's own error
   body (a genuinely useful message, unlike a bare 429): exact tokens
   used, exact retry time.
2. Attempted Gemini as an emergency fallback (already had it certified
   `yellow` from earlier) — Gemini's `gemini-flash-latest` free tier
   ALSO hit its own daily cap (20 requests/day — a very small bucket)
   at nearly the same time.
3. Added OpenRouter as a third emergency link (`nvidia/nemotron-...
   :free` via their free-model pool) — worked initially, but also hit
   its own daily free-request cap under continued load.
4. **All three real providers were simultaneously exhausted at least
   once tonight.** This is the actual, lived proof that free-tier
   quotas are a genuine, real constraint at even modest real usage —
   not a hypothetical scaling concern.

**Real regression, self-inflicted, worth remembering the lesson:**
When `llm_router.py` was rewritten from scratch earlier tonight to add
`TOOL_CALL_FALLBACK_CHAIN`, it was built from an already-stale local
copy — which didn't have the EARLIER emergency SSH-only fix to the
`agent_turn` chain (adding Gemini as a fallback there). Deploying the
"new" file silently REVERTED that fix without anyone noticing, because
it looked like a clean addition, not a regression. Cost real time to
diagnose. **Lesson, stated plainly for next time: whenever rewriting a
whole file from scratch instead of a targeted `str_replace`, diff it
against what's actually live first — don't assume the rest is
unchanged.**

**Real, important safety-net fix added:** `main.py`'s final `ask_llm()`
call had NO error handling at the top level — if every provider in the
chain failed simultaneously (which happened live tonight), the customer
got total silence (a failed request), not even an error message. Added
a try/except around this specific call: on complete provider failure,
the customer now gets a warm, honest "having trouble right now, please
contact us directly" message instead of nothing. This is arguably the
single most important fix of this whole session — it's the difference
between a degraded demo and a broken one.

**Real, found-live bug in the OpenRouter integration:** initially wired
to `openrouter/free` (their auto-router, which silently picks a
different underlying model every call). It leaked raw internal
reasoning/safety text ("User Safety: safe") directly into a real
customer-facing reply — different free models format output
differently, and nothing stripped this out. Fixed by pinning to one
specific, known model (`nvidia/nemotron-3-nano-30b-a3b:free`) instead
of the auto-router, trading a little robustness (this exact model could
itself get pulled from the catalog someday) for predictable, clean
output — the right trade for a customer-facing reply.

**Mitigations applied, in order, once the outage was actively hurting
the demo:**
1. Marked Gemini `yellow` (emergency use) via `model_registry` — no
   restart needed, `route()` reads this table fresh every message.
2. Discovered Groq's actual Developer/paid tier upgrade was ITSELF
   temporarily unavailable ("due to high demand") — not something we
   could route around, purely Groq's own outage.
3. Checked all three providers' live status directly rather than guess
   — found Groq had already reset on its own, and `gemini-flash-lite-
   latest` (a DIFFERENT model, separate quota bucket from the exhausted
   `gemini-flash-latest`) was working. Swapped to it.
4. Both bots confirmed responding again; demo continued the next day.

**Also completed tonight: the demo tenant.** Fictional "Glow Beauty
Studio & Store" — deliberately combines BOTH templates (retail products
+ salon booking) in one tenant, since that's a realistic real-world
pairing and lets one conversation demonstrate both capabilities. Found
and fixed three real schema mistakes while building it (wrong column
name `price` vs. actual `price_inr_per_unit`; wrong `stock_status`
values — real constraint uses `in_stock`/`low_stock`/`out_of_stock`
with underscores, not spaces — found by directly querying
`pg_get_constraintdef` instead of guessing a third time). Validated
directly (no bot stood up — deliberate, given the rate-limit chaos):
both a product question and a booking request answered correctly
against the same tenant.

**New generic artifact: `booking_template_GENERIC_schema.sql`** — the
same proven 8-table structure, fully placeholder-ized
(`<tenant-slug>`, `<Resource 1 name>`, etc.), for any future
appointment-based tenant. Also extended `booking_tools.build_services_
catalog_text()` to include retail products alongside services, for any
tenant (like the demo one) that sells both.

**Known gap, real and current:** all three free-tier providers can be
exhausted simultaneously under real, non-malicious usage in a single
evening. The graceful-fallback safety net means this now degrades to
"please contact us" instead of silence, but it's still a real
availability risk worth solving properly — either a paid tier (Groq's
Developer tier: no minimum, ~$0.59/$0.79 per million tokens for the
70B model, likely a few dollars/month at current volume, but currently
blocked by Groq's own signup outage) or a genuinely unlimited local
GPU-hosted model (the ORIGINAL plan in `llm_router.py`'s own comments,
removed only because RunPod/dslab weren't reliable — this incident is
direct, lived proof of why that plan existed in the first place).

**NEXT (updated again):**
1. Revisit the Groq Developer tier upgrade once their signup outage
   clears — likely the fastest, cheapest real fix for provider
   exhaustion (estimated a few dollars/month at current volume).
2. OR: get a reliable GPU (rented or owned) for local inference — the
   actual unlimited, zero-rate-limit answer, deferred until now because
   of unreliability; tonight is real evidence the deferral has a cost.
3. Docker: shared image, per-tenant containers (still not started —
   would ALSO have prevented tonight's stale-file-overwrite regression,
   since a rebuilt image is explicit, not an assumed-clean local copy).
4. `my_dance_academy` — next tenant, starting fresh next session.
5. Everything from parts 1 and 2's NEXT lists that's still open:
   Rajesh Bhai (real vendor), Gaurav (founder identity), Sunita Plastics
   (blocked on real business info), `founder_reports.py` stale tenant,
   CI/CD, real eval-engine deployment.
6. Consider whether to stop running eval/diagnostic scripts during
   active demo windows going forward — tonight's own testing volume was
   part of what drove the quota exhaustion.
## 2026-08-01 — Session (evening, ~4 hours)

- Baseline git snapshot completed for all three tenant folders (Keshri
  Pipes, Mihika's Studio, My Dance Academy) — Dance Academy git-init'd
  for the first time, `.env`/`venv`/`chroma_db` correctly gitignored
  everywhere, no secrets committed
- Bug A (hardcoded "haircut" example in shared `_system_prompt()`)
  diagnosed as a copy-paste bug, NOT a cross-tenant leak — fixed and
  deployed across all three tenants
- NEW bug found live (not on any prior plan): vendor-forwarding was
  either falsely denying real catalog items or falsely claiming a
  forward happened when it hadn't, and leaking internal founder-facing
  text to customers. Fully diagnosed and fixed through several iterations
  (catalog-vs-vendor-vs-decline three-way split, full-word-coverage
  matching, matching on customer's actual words not the LLM's invented
  vendor-category label, clean customer-facing copy) — confirmed working
  end to end via live Telegram tests
- Company profile (`company_profile.md`) updated to direct full-catalog
  requests to the real website (https://keshripipes.com) instead of the
  model improvising a fallback — reloaded into Supabase, confirmed live
  after a gateway restart (discovered: `load_company_profile.py` does
  NOT auto-clear `resolve_tenant()`'s cache, a restart is required)
- NEW FEATURE shipped: payment follow-up reminders for Keshri Pipes.
  New `payment_followups` table, new `payment_tools.py` (owner-triggered
  send + customer-reply classification: DELAYED/READY/OTHER), hooked
  into `telegram_webhook`, state-gated so it can never touch a customer
  who wasn't actually sent a reminder. DELAYED path tested live and
  confirmed correct end to end (DB state + Telegram round-trip). READY
  path and 3rd-follow-up escalation are written and deployed but NOT
  yet live-tested — do that first next session.
- Founder decision: Docker + CI/CD is now the top priority for next
  session, ahead of any new tenant work — tonight reconfirmed the risk
  (a single missing `import re` briefly broke live order-forwarding
  mid-fix; several other near-misses from manual SSH patching)
- Founder decision: NXT Landspaces (tenant #5, real estate) is parked
  for now — do not start scaffolding without being asked
- All commits pushed to `origin/droplet-live` on GitHub (was 4 commits
  behind at session start, caught up by end)
- NEXT: test payment-followup READY + escalation paths, then Docker/CI-CD
  design discussion, then Bug B (My Dance Academy dateless "11am" loop —
  still not diagnosed across three sessions now), then `/opt/jarvis-frontend`
  investigation
