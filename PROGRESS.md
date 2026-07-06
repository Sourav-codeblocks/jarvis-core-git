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