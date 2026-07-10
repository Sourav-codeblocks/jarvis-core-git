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
