# Jarvis Core — Architecture (living document)

**This file is REWRITTEN, not appended to.** `PROGRESS.md` is the diary —
it grows forever and that's fine. This file is the map — it should always
be short enough to read in five minutes and describe *only* what's true
right now.

Last rewritten: 2026-07-23, after the owner-tools/vendor-forwarding session.
Anything marked **[unverified]** wasn't opened this pass — confirm before
relying on it.

---

## The One Rule

`tenant_id` (or `tenant_slug` at the edge) flows through every table,
every Chroma collection, every WebSocket route. Tenant #2 should be a
config row + a YAML file, never a code change. True for the gateway/voice/
chat path. **Not yet true for `founder_reports.py`** — still hardcodes
`TENANT_ID = 1`, a fixed rewrite exists on the laptop, never deployed.

---

## Deployment reality (verified on droplet)

Droplet `159.89.166.167` (`jarvis-core-gateway`), `/opt/jarvis-core`.
**Now under real git version control** (`droplet-live` branch, bootstrapped
2026-07-22 — previously zero history, deploys were manual file copies).
Two systemd services: `jarvis-gateway.service`, `jarvis-frontend.service`.

The full eval/certification engine (`eval_api.py`, `eval_graph.py`,
`certify_model.py`, etc.) remains **local-only, never deployed** — same as
last rewrite, unchanged tonight.

---

## Component map

| File | Role | Status |
|---|---|---|
| `main.py` | Gateway. Telegram webhook, `/health`, `/api/founder/reports*`, mounts founder/voice/tts routers, tenant-dynamic via `resolve_tenant(TENANT_SLUG)`. **Now also resolves owner identity per message and branches to tool-calling for admin/founder before falling back to the grounded reply.** Role-aware persona (owner tone vs. customer tone) and role-aware action guardrail. | **Live**, patched 2026-07-23 |
| `owner_tools.py` | **NEW.** Channel abstraction (`send_channel_message` — Telegram real, WhatsApp cleanly stubbed), `resolve_identity_role()` (checks `channel_links`→`identities`), `forward_to_vendor()` tool with deterministic, code-decided result text (never LLM-narrated), Groq-based tool-decision layer (`decide_and_run_owner_tool`), same proven pattern as `founder_ws.py`. | **Live** |
| `founder_ws.py` | Founder chat brain (voice/typed via Founder's Core). `route_founder_query()`. | **Live**, null-args crash fixed 2026-07-22 |
| `voice_bridge.py` / `tts.py` | Voice in/out for Founder's Core. | **Live.** `tts.py` hardcodes an **English-only** Deepgram voice (`aura-2-helena-en`) — root cause of garbled Hindi speech reported 2026-07-22, not yet fixed. |
| `llm_router.py` / `providers.py` | Model routing + provider wrappers. | **Live**, unchanged |
| `toleration.py` | Strike/moderation system. | **Still dead code** — file exists, never imported in `main.py`. Unchanged. |
| `founder_reports.py` | REST reports (`/api/founder/reports*`). | **Live, still stale** — hardcoded `TENANT_ID = 1`. Unchanged. |
| `catalog_store.py` / `ingest.py` | `products` table ↔ Chroma sync. | **Live**, unchanged. `FULL_CATALOG_PATTERNS` regex confirmed too narrow — misses natural phrasing like "pura product list dena" (only matches "pura" directly adjacent to "catalog/list"). Found 2026-07-22, not yet fixed. |

---

## Identity & roles — REPLACED tonight, read carefully

**As of 2026-07-23, `identities` + `channel_links` is the real, live
authorization system — not `users.role`.**

History, so this doesn't get re-litigated: `users.role` (`customer` /
`employee` / `owner`) was added earlier on 2026-07-23 as a first pass.
Mid-session, a pre-existing, more complete system was discovered —
`identities` (admin/founder/staff roles) + `channel_links` (lets one
person link multiple channels — Telegram *and* WhatsApp — to one
identity), migrated back on 2026-07-14 but **never wired to any code path**
(`channel_links` had zero rows until tonight). Decision: adopt the older,
better-designed system as the real one going forward. `users.role` is left
in place (harmless) but **no code should read it for authorization** —
treat it as superseded.

```
identities: id=1 Sourabh — role='admin'
            id=2 Nikunj Goel — role='founder'
channel_links: both linked to their real Telegram chat_ids
```

`owner_tools.resolve_identity_role(channel, channel_user_id)` is the one
function that answers "is this an owner-level person" — looks up
`channel_links` → `identities`, returns `(None, None)` for the
overwhelmingly common case (an ordinary customer), or `(role, display_name)`
for admin/founder/staff. Revoked/pending identities are treated identically
to no-identity — never surfaced as an error to the person.

**Gaurav is not yet seeded** — no known Telegram chat ID for him yet.

---

## `vendors` table — NEW tonight

Tenant-scoped, loose category matching (`find_vendor()` does substring
match in both directions, not exact string equality — vendor categories
are free text). Currently seeded with exactly one row: **Sourabh himself**,
under `category='cement'`, so the feature could be tested end-to-end
without a real vendor yet. **Rajesh Bhai (the real intended cement vendor)
is not yet seeded** — need his real Telegram chat ID.

---

## Owner-tool flow (Telegram, admin/founder only)

```
Telegram message → main.py webhook → resolve_identity_role()
  → if admin/founder:
      owner_tools.decide_and_run_owner_tool() [Groq tool-decision call]
        → tool fires → forward_to_vendor() → find_vendor() → send_channel_message()
          → result_text is DECIDED IN CODE from the real delivery outcome,
            never left to the LLM to narrate (this is the actual fix for
            the false-action-confirmation bug below)
        → no tool fires → falls through to the normal ask_llm() reply,
          with a role-aware persona and a role-aware action guardrail
  → if ordinary customer: skips straight to ask_llm(), unchanged behavior
```

**Confirmed working live** (2026-07-23): "send 550 bori of cement to
nagesh in kota, forward this message to vendor" → correct field extraction
→ real Telegram delivery to the seeded test vendor → correct, honest
confirmation text.

**Not yet tested**: `forward_to_vendor` when no vendor exists for the
requested category. Should hit `find_vendor()`'s `None` path and reply
honestly that no vendor is registered — worth confirming live before
Nikunj/Gaurav use this for real.

---

## Known gaps (current)

1. **Conversation memory window is short** (`get_recent_history()`, 8
   messages) — confirmed live 2026-07-23: asking "did that work?" a few
   turns after a successful forward got an honest-but-wrong "I don't have
   confirmation," because the real confirmation had scrolled out of the
   window. Not a new bug, same root cause tracked since 2026-07-22
   (founder path has the identical gap).
2. **`FULL_CATALOG_PATTERNS` regex too narrow** — misses natural phrasing.
   Found 2026-07-22, not yet fixed.
3. **`tts.py` hardcodes an English-only voice** — root cause of garbled
   Hindi TTS. Found 2026-07-22, not yet fixed.
4. **`founder_reports.py` still stale** (`TENANT_ID = 1` hardcoded).
5. **`toleration.py` still dead code.**
6. **Eval/certification engine still entirely undeployed.**
7. **`chroma_db` name mismatch** (kesari vs. keshri) — still unresolved.
8. **Gaurav not yet seeded as a `founder` identity** — no Telegram ID on
   file yet.
9. **Rajesh Bhai not yet seeded as a real vendor** — `vendors` table only
   has the Sourabh test row.
10. **`forward_to_vendor`'s no-vendor-found path is untested in production**
    (see above).
11. `get_revenue_report`, `get_runway_report`, `get_pipeline_report`
    (founder voice path) are still fixtures — no real orders/CRM/finance
    tables exist.

---

## Quick reference — "where do I go to change X?"

| Want to... | Edit |
|---|---|
| Add a new owner-only tool (Telegram) | `owner_tools.py` — add to `OWNER_TOOLS_SCHEMA` + `decide_and_run_owner_tool`'s dispatch, and wire the function itself |
| Add a new founder tool (voice/typed, Founder's Core) | `founder_ws.py` — `FOUNDER_TOOLS` (separate tool set, deliberately not shared with `owner_tools.py`) |
| Promote someone to admin/founder | `identities` + `channel_links` rows — **not** `users.role`, that's superseded |
| Add a vendor | `vendors` table row — `category` is free text, matched loosely |
| Change which model handles a task | `llm_router.py`'s `MODEL_MATRIX` |
| Fix the Hindi TTS voice | `tts.py`'s `DEEPGRAM_TTS_URL` — needs a Hindi-capable Aura voice or a language-aware branch |
| Fix "full catalog" not matching natural phrasing | `main.py`'s `FULL_CATALOG_PATTERNS` regex |
