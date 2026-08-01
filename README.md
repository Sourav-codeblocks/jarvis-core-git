# Jarvis Core — Multi-Tenant Agentic Platform

This is the foundation of a multi-tenant platform where each small
business ("tenant") gets a Telegram (soon WhatsApp) chatbot answering
customers grounded in their own real data — never hallucinated. Adding a
tenant is meant to be config + data, never code.

**Status as of 2026-08-01**: three tenants live on Telegram (Keshri
Pipes, Mihika's Studio, My Dance Academy), each in its own folder/port/
systemd service on one DigitalOcean droplet. See `ARCHITECTURE.md` for
the current map (rewritten each session, short by design) and
`PROGRESS.md` for the full dated history — this file gives orientation
and the reference tables; it no longer tries to be a second running log.
A detailed dated narrative of the RunPod era, the eval engine build, and
the 2026-07 provider-fallback work still lives further down for
historical context, but treat `ARCHITECTURE.md` as more current for
anything about what's actually running today.

## ⚠️ Next major change: Docker + CI/CD (not started)

Founder decision, 2026-08-01: this is the top priority for the next
session. Current deployment (below) is four separate folders on one
droplet, kept in sync by hand — a real, repeatedly-confirmed source of
fragility (a missing `import re` briefly broke live order-forwarding
mid-session tonight; several other close calls came from manual SSH
patching). Don't assume the folder-per-tenant/systemd model described
below is permanent — it's the current reality, expected to change soon.

## The One Rule
**`tenant_id` flows through everything** — every table, every Chroma
collection, every usage log row. This is the difference between a
platform and a pile of scripts.

## Live infrastructure (current, 2026-08-01)

| Piece | Where | Notes |
|---|---|---|
| Keshri Pipes gateway | `/opt/jarvis-core`, port 8000, `jarvis-gateway.service` | Original tenant, catalog template, has payment follow-ups (new) |
| Mihika's Studio gateway | `/opt/jarvis-core-mihika`, port 8001, `jarvis-gateway-mihika.service` | Booking template |
| My Dance Academy gateway | `/opt/jarvis-core-dance`, port 8002, `jarvis-gateway-dance.service` | Booking template |
| Frontend | `/opt/jarvis-frontend`, port 3000, `jarvis-frontend.service` | **Unverified** — see open discrepancy note in `ARCHITECTURE.md` (may or may not be the same thing as `founders-core/` described later in this file) |
| Droplet | `159.89.166.167`, 2GB RAM / 2vCPU / 60GB disk | DigitalOcean |
| Database | Supabase (Mumbai region) | All tenant data, `payment_followups` added 2026-08-01 |
| Reverse proxy | nginx on the droplet | Routes each tenant's `/webhook/telegram` path to its own port |
| LLM providers | Groq (primary), Gemini, OpenRouter (fallback chain) | See Model Routing below — **[unverified this pass]**, confirm current chain in `llm_router.py` directly before relying on this table |

**⚠️ Run the gateway on the droplet, not on your Mac.** Local `uvicorn
--reload` only ever talks to your laptop's own `.env`/`chroma_db` — it
will look like a change worked while production stays on the old code.
To ship a real change:

```bash
ssh root@159.89.166.167
cd /opt/jarvis-core          # or whichever tenant folder
# make your change (see COMMANDS.md for the safe patch-script pattern)
sudo systemctl restart jarvis-gateway
sudo systemctl status jarvis-gateway --no-pager   # confirm it came back up clean
```

## The Switchbox
The `tenant_tools` table is the per-tenant feature toggle — enable/
disable channels and integrations per tenant without touching code.

## Tenants (current, 2026-08-01)

| Tenant | Type | Bot live? | Notes |
|---|---|---|---|
| Keshri Pipes | Catalog | Yes | Most-tested, has git+remote, payment follow-ups (new) |
| Mihika's Studio | Booking | Yes | Git, no remote yet |
| My Dance Academy | Booking | Yes | Git added 2026-08-01 |
| Demo tenant | Catalog+Booking | No, deliberately | Fictional data-only tenant |
| Sunita Plastics | Unknown | Not started | Blocked on real business info |
| NXT Landspaces | Leads+Booking (real estate) | Not started | Fully spec'd, explicitly parked |

## Payment follow-up reminders (new, 2026-08-01, Keshri Pipes only)

Owner can trigger "send payment reminder to X"; customers replying to an
open reminder get classified (delayed / ready-to-pay / other) and the
system updates state and, for ready-to-pay replies, alerts the founder(s)
directly. Full detail in `ARCHITECTURE.md`. Not yet ported to other
tenants — it's catalog-tenant-specific, not needed by the booking
templates.

## Known open bugs (2026-08-01)

- **Dateless booking loop on "11 am"** (My Dance Academy) — still not
  diagnosed across three sessions. See `ARCHITECTURE.md` for detail.
- Everything else marked resolved in the last few sessions — see
  `ARCHITECTURE.md`'s "Known gaps" section for the current, honest list
  rather than trusting this file's older dated entries below, which are
  historical and may no longer reflect reality.

## Files
- `schema.sql` — multi-tenant foundation. **[unverified]** — has
  historically drifted behind the live Supabase schema (e.g. `messages`
  table existed live before it was ever added to this file); confirm
  against real Supabase columns before trusting it fully.
- `main.py` — the gateway, per tenant folder
- `owner_tools.py` — owner-only tools (vendor forwarding, payment
  reminders as of 2026-08-01)
- `payment_tools.py` — new 2026-08-01, Keshri Pipes only
- `booking_tools.py` — availability engine + booking creation (booking-
  template tenants)
- `catalog_store.py` — structured product truth (Supabase `products`
  table), Chroma as a derived semantic index
- `llm_router.py` / `providers.py` — model routing + fallback chains
- `toleration.py` — strike system, Telegram path
- `ARCHITECTURE.md` — the current map, rewritten each session
- `PROGRESS.md` — the full dated diary
- `COMMANDS.md` — command reference, updated 2026-08-01 for the current
  droplet-based workflow (the ngrok/local-dev section below is historical)

---

## Historical narrative (RunPod era, eval engine build — for context only)

The sections below describe the 2026-07 sessions that got this platform
from local dev to a real deployment, including the eval/certification
engine and a full compute-provider outage (RunPod terminated mid-project,
recovered onto a free-cloud fallback chain). This is kept for context on
*why* certain design decisions exist (e.g. the fallback chain + green/
yellow/red certification gate in `llm_router.py`), but the specific
status claims in this section are **not current** — treat `PROGRESS.md`
and `ARCHITECTURE.md` as the source of truth for what's true today.

**2026-07-13**: RunPod (the original GPU compute provider) was
terminated mid-project, taking production down. Root cause identified:
zero resilience from depending on a single compute provider. Fix: wire
`main.py` and `founder_ws.py` through `llm_router.route()` with a real
free-cloud fallback chain (Groq → Gemini → OpenRouter), gated by a
certification system (`certify_model.py` / `model_registry`) that
refuses to route to any unverified model. Landed same day; bot confirmed
live again.

**2026-07-14**: Both LLM paths fully off RunPod. Structured catalog
truth (`products` table in Supabase, Chroma as derived index) built to
fix product-code retrieval bugs found via real customer screenshots.
`eval_customer_bot.py` (end-to-end regression suite against the real
pipeline) green at 8/8.

**Eval engine** (`eval_cases.py`, `eval_graph.py`, `certify_model.py`,
and related files): a separate, out-of-band system for grading candidate
models before promotion into the live routing table. Two verdict stores
existed at last check (`model_catalog` from an earlier CRAFT-based flow,
`model_registry` from the certification gate) with a flagged but
unresolved reconciliation need — **[unverified]**, confirm current state
before relying on either.

For the full session-by-session account of this period, see
`PROGRESS.md`'s 2026-07-10 through 2026-07-14 entries.
