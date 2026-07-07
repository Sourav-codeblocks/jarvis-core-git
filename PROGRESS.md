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

## 2026-07-07 — Session (morning)
- Git repo initialized and pushed to GitHub: Sourav-codeblocks/jarvis-core-git (private)
  - Added .gitignore (chroma_db/, __pycache__/, .DS_Store, .env) — none of these were
    ever exposed; .env confirmed never tracked
  - jarvis-core and JARVIS HUD (Lovable) are separate repos by design — HUD is a
    frontend shell that will call this backend's API, not share a codebase
- CONFIRMED: messages table exists live in Supabase (20 real records, bot working
  fine) — schema.sql was just never synced. Fixed: added messages table definition
  to schema.sql, pushed. No functional bug, was a documentation drift issue only.
- FIXED + VERIFIED: ingest.py dedup bug — doc_id was content-hash-based, so any
  price/stock change created a duplicate vector instead of overwriting. Changed to
  doc_id = product_id. Verified via full chroma_db wipe + re-ingest: 15 products in
  CSV -> 15 documents in collection (previously was showing 30, i.e. stale dupes
  from the old hash scheme). Committed + pushed.
- FIXED + VERIFIED: llm_router.py KeyError — providers[provider_name] lookup was
  outside the try block, so a missing provider key crashed the whole router instead
  of falling through the chain. Moved lookup inside try. Verified with a throwaway
  test script simulating a missing anthropic_api key: router now correctly raises
  AllProvidersFailed instead of a raw KeyError. Committed + pushed.
- Discussed: Lovable AI for a sci-fi voice-HUD frontend ("JARVIS") with mic + call
  buttons, wired later to this backend's router (voice command -> intent -> Telegram
  or n8n/email route). Free tier likely sufficient for v1 prototype. Login via
  GitHub (not Gmail) for continuous export/self-hosting. Prompt for the visual
  shell already written and used — Lovable connected to GitHub
  (Sourav-codeblocks org), no repo linked yet (expected, HUD project not started).
- STILL OPEN — RLS is disabled on all Supabase tables (flagged again, same as
  2026-07-05 note). Not urgent with one tenant, but must fix before onboarding
  tenant #2 or exposing beyond Kesari.
- STILL OPEN from code_review.md, in priority order:
  1. RLS enablement on Supabase tables
  2. Hardcoded tenant seams in main.py (tenant_slug, tenant_id: 1, global Chroma
     collection, single TELEGRAM_BOT_TOKEN)
  3. toleration.py missing db interface (get_moderation_state, increment_offtopic,
     set_hard_ignore not implemented anywhere)
  4. kesari vs keshri spelling reconciliation across schema.sql seed / main.py
     hardcoded values / live DB
- NEXT: pick up RLS or main.py tenant-seam fixes next backend session. Separately,
  start building the JARVIS HUD in Lovable (new chat thread).