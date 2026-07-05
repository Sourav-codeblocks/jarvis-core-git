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